"""演示模式 + 设备对接路由"""
import uuid
import base64
import random
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import UPLOADS_DIR
from ..models.upload import UploadRecord
from ..models.ocr import OCRResult
from ..models.sorting import SortingDecision
from ..services.sim_generator import SimPackageGenerator
from ..services.image_pipeline import ImagePipelineService
from ..services.sort_engine import SortRuleEngine
from ..services.damage_detector import DamageDetector
from ..models.exception import ExceptionRecord
from ..websocket.manager import manager

router = APIRouter(prefix="/api/demo", tags=["演示模式"])

device_router = APIRouter(prefix="/api/device", tags=["设备对接"])


class DemoGenerateRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=40, description="生成数量 1-40（秒返＋后台OCR）")
    damage_rate: float = Field(default=0.15, ge=0, le=1.0, description="破损占比 0-1（0=无破损，1=全部破损）")


class DeviceFeedRequest(BaseModel):
    image_base64: str = Field(..., description="Base64编码的图片数据")
    device_id: str = Field(default="CAM-001", description="设备编号")
    timestamp: str | None = Field(default=None, description="采集时间 ISO格式")


@router.post("/generate")
async def demo_generate(
    req: DemoGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """一键生成模拟包裹 → 后台自动走通全流程，页面秒返"""
    total = req.count
    file_ids = []
    uploads_dir = str(UPLOADS_DIR)

    # Step 1: 快速生成图片+入库（不等待OCR）
    for i in range(total):
        try:
            rel_path, fields = SimPackageGenerator.generate(uploads_dir)
            file_id = uuid.uuid4().hex
            abs_path = UPLOADS_DIR / rel_path
            record = UploadRecord(
                file_id=file_id, original_name=Path(rel_path).name,
                file_path=rel_path, file_size=abs_path.stat().st_size if abs_path.exists() else 0,
                mime_type="image/jpeg", uploader_id=1, status="done",
                package_length=fields.get("length"),
                package_width=fields.get("width"),
                package_height=fields.get("height"),
            )
            db.add(record); db.commit(); db.refresh(record)
            file_ids.append({"file_id": file_id, "rel_path": rel_path, "fields": fields})
        except Exception:
            pass

    # Step 2: 后台异步处理OCR+分拣+破损检测
    background_tasks.add_task(_bg_process_batch, file_ids, req.damage_rate)

    return {
        "code": 200,
        "message": f"{len(file_ids)} 张已入库，后台处理中",
        "data": {"total": total, "created": len(file_ids), "status": "processing", "damage_rate": req.damage_rate},
    }


def _bg_process_batch(file_ids: list, damage_rate: float = 0.15):
    """后台批量处理OCR+条码+分拣+随机异常 — 强制校验南昌分区"""
    from ..database import SessionLocal
    import random
    from sqlalchemy import func
    db = SessionLocal()

    # 批次级随机参数（破损占比由前端控制，其余随机）
    blur_rate = random.uniform(0, 0.5)
    scribble_rate = random.uniform(0, 0.6)
    ocr_fail_rate = random.uniform(0, 0.2)

    # 统计
    stats = {"total": len(file_ids), "valid": 0, "invalid_dest": 0, "duplicates": 0, "errors": 0}

    try:
        for item in file_ids:
            fid = item["file_id"]
            rel_path = item["rel_path"]
            fields = item.get("fields", {})
            try:
                from ..services.ocr_service import OCRService
                abs_path = str(UPLOADS_DIR / rel_path)

                # ===== 条码解码（在图像效果之前，保证清晰条码可被识别） =====
                barcode_data = fields.get("tracking_number", "")
                try:
                    from ..services.barcode_service import BarcodeService
                    br = BarcodeService.decode(abs_path)
                    barcodes = br.get("barcodes", [])
                    if barcodes:
                        from ..models.barcode import BarcodeResult
                        first = barcodes[0]
                        db.add(BarcodeResult(file_id=fid, barcode_type=first["type"], barcode_data=first["data"],
                            rect_x=first["rect"]["x"], rect_y=first["rect"]["y"],
                            rect_w=first["rect"]["w"], rect_h=first["rect"]["h"],
                            total_count=br["total_count"], fusion_result=br["fusion_result"]))
                        db.commit()
                    elif barcode_data:
                        # pyzbar 失败时用已知运单号写入条码结果（兜底）
                        from ..models.barcode import BarcodeResult
                        db.add(BarcodeResult(file_id=fid, barcode_type="CODE128", barcode_data=barcode_data,
                            total_count=1, fusion_result="barcode"))
                        db.commit()
                except Exception:
                    if barcode_data:
                        try:
                            from ..models.barcode import BarcodeResult
                            db.add(BarcodeResult(file_id=fid, barcode_type="CODE128", barcode_data=barcode_data,
                                total_count=1, fusion_result="barcode"))
                            db.commit()
                        except Exception: pass

                # 模拟模糊
                if random.random() < blur_rate:
                    try:
                        import cv2, numpy as np
                        img = cv2.imread(abs_path)
                        if img is not None:
                            img = cv2.GaussianBlur(img, (15,15), 10)
                            cv2.imwrite(abs_path, img, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    except: pass

                # 模拟涂鸦
                if random.random() < scribble_rate:
                    try: SimPackageGenerator._add_scribble(abs_path)
                    except: pass

                r = OCRService.recognize(abs_path)
                # 模拟极端OCR失败
                if random.random() < ocr_fail_rate:
                    r = {"raw_text":"","fields":{},"processing_time_ms":r.get("processing_time_ms",0),"status":"manual_required"}

                # OCR识别不完整时，用生成数据补全字段 + 修正 not_waybill 状态
                if r.get("status") == "not_waybill" and fields.get("tracking_number"):
                    r["status"] = "need_review"  # 图像有破损但数据已知，降级为需复核

                # ===== 目的地校验：强制限定南昌各区 =====
                ocr_fields = r.get("fields", {})
                ocr_province = ocr_fields.get("province", "") or fields.get("province", "")
                ocr_city = ocr_fields.get("city", "") or fields.get("city", "")
                ocr_district = ocr_fields.get("district", "") or fields.get("district", "")

                # 如果OCR识别不完整，用生成时的fields补全
                if not ocr_province and fields.get("province"):
                    ocr_province = fields["province"]
                if not ocr_city and fields.get("city"):
                    ocr_city = fields["city"]
                if not ocr_district and fields.get("district"):
                    ocr_district = fields["district"]

                is_valid_dest = SimPackageGenerator.is_valid_nanchang_destination({
                    "province": ocr_province, "city": ocr_city, "district": ocr_district,
                })

                if not is_valid_dest:
                    stats["invalid_dest"] += 1
                    # 标记为需人工复核
                    if r.get("status") == "auto_pass":
                        r["status"] = "need_review"

                # ===== 去重：检查是否已存在相同运单号 =====
                tn = ocr_fields.get("tracking_number", "") or fields.get("tracking_number", "")
                if tn:
                    existing = db.query(OCRResult).filter(OCRResult.tracking_number == tn).first()
                    if existing:
                        stats["duplicates"] += 1
                        continue  # 跳过重复包裹

                ocr = OCRResult(file_id=fid,
                    raw_text=r.get("raw_text",""),
                    receiver_name=ocr_fields.get("receiver_name","") or fields.get("receiver_name",""),
                    phone=ocr_fields.get("phone","") or fields.get("phone",""),
                    province=ocr_province,
                    city=ocr_city,
                    district=ocr_district,
                    detail_address=ocr_fields.get("detail_address",""),
                    tracking_number=tn,
                    processing_time_ms=r.get("processing_time_ms",0),
                    status=r.get("status","manual_required"))
                db.add(ocr); db.commit()

                # 随机破损（类型随机，可叠加多种）
                damage_types = ["damage","deformed","leak","stain"]
                if random.random() < damage_rate:
                    applied = set()
                    for _ in range(random.randint(1,3)):
                        dt = random.choice(damage_types)
                        if dt in applied: continue
                        applied.add(dt)
                        try:
                            SimPackageGenerator.add_damage_effect(abs_path, dt)
                            detect = DamageDetector.detect(abs_path)
                            if detect.get("damaged"):
                                exc_type = detect["issues"][0]["type"] if detect.get("issues") else dt
                                existing = db.query(ExceptionRecord).filter(
                                    ExceptionRecord.file_id==fid,
                                    ExceptionRecord.exception_type==exc_type,
                                    ExceptionRecord.status=="pending").first()
                                if not existing:
                                    db.add(ExceptionRecord(file_id=fid,exception_type=exc_type,
                                        detail=str(detect.get("issues",[])),status="pending"))
                                    db.commit()
                        except: pass

                SortRuleEngine.decide(fid, db)
                stats["valid"] += 1

            except Exception as e:
                stats["errors"] += 1
                print(f"[BG_BATCH] failed for {fid}: {e}")
                db.rollback()
                try:
                    upload = db.query(UploadRecord).filter(UploadRecord.file_id==fid).first()
                    if upload: upload.status="failed"; db.commit()
                except: pass
    finally:
        db.close()
        print(f"[BG_BATCH] 完成: 总数{stats['total']} 成功{stats['valid']} "
              f"无效目的地{stats['invalid_dest']} 去重{stats['duplicates']} 失败{stats['errors']}")


# ==================== 数据清理 API ====================

class CleanupRequest(BaseModel):
    dry_run: bool = Field(default=True, description="True=仅分析不删除")


@router.get("/data-quality")
def check_data_quality(db: Session = Depends(get_db)):
    """分析当前数据库中包裹数据质量（非南昌目的地、重复、孤立记录）"""
    from ..services.data_cleanup import analyze_data_quality
    issues = analyze_data_quality(db)
    return {
        "code": 200,
        "message": "数据质量分析完成" if issues["is_clean"] else f"发现 {issues['total_issues']} 个问题",
        "data": issues,
    }


@router.post("/cleanup")
def cleanup_invalid_data(req: CleanupRequest, db: Session = Depends(get_db)):
    """清理非南昌目的地包裹 + 去重 + 孤立记录

    dry_run=true: 仅统计不删除（安全预览）
    dry_run=false: 实际执行删除，不可撤销！
    """
    from ..services.data_cleanup import cleanup_invalid_packages
    result = cleanup_invalid_packages(db, dry_run=req.dry_run)

    if req.dry_run:
        result["warning"] = "仅预览模式，未实际删除。将 dry_run 设为 false 执行清理。"

    total_invalid = result.get("invalid_ocr_count", 0)
    if total_invalid == 0 and result.get("duplicates_removed", 0) == 0:
        return {"code": 200, "message": "数据已清洁，无需清理", "data": result}

    return {
        "code": 200,
        "message": f"{'[预览] ' if req.dry_run else ''}发现 {total_invalid} 条无效记录 + {result.get('duplicates_removed', 0)} 条重复",
        "data": result,
    }


class MobileUploadRequest(BaseModel):
    image_base64: str = Field(..., description="Base64编码的图片数据")
    device_id: str = Field(default="MOBILE-001", description="设备编号")


@device_router.post("/upload")
async def mobile_upload(
    req: MobileUploadRequest,
    db: Session = Depends(get_db),
):
    """手机拍照秒传（不等待OCR，立即返回file_id）"""
    img_data = req.image_base64
    if "," in img_data and img_data.startswith("data:"):
        img_data = img_data.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(img_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Base64解码失败: {e}")
    if len(img_bytes) == 0:
        raise HTTPException(status_code=400, detail="图片数据为空")

    file_id = uuid.uuid4().hex
    now = datetime.now()
    date_dir = now.strftime("%Y-%m")
    abs_dir = UPLOADS_DIR / date_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    filename = f"mobile_{file_id[:8]}.jpg"
    rel_path = f"{date_dir}/{filename}"
    with open(UPLOADS_DIR / rel_path, "wb") as f:
        f.write(img_bytes)

    record = UploadRecord(
        file_id=file_id,
        original_name=filename,
        file_path=rel_path,
        file_size=len(img_bytes),
        mime_type="image/jpeg",
        uploader_id=1,
        status="done",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

@device_router.post("/upload-file")
async def mobile_upload_file(
    file: UploadFile = None,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """手机拍照上传（压缩+后台OCR，秒返file_id）"""
    from fastapi import BackgroundTasks
    if not file:
        raise HTTPException(status_code=400, detail="无文件")
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # 图片压缩
    try:
        import cv2, numpy as np
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            h, w = img.shape[:2]
            if max(w, h) > 2000:
                scale = 2000 / max(w, h)
                img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
            _, encoded = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if encoded is not None: contents = encoded.tobytes()
    except Exception: pass

    file_id = uuid.uuid4().hex
    date_dir = datetime.now().strftime("%Y-%m")
    (UPLOADS_DIR / date_dir).mkdir(parents=True, exist_ok=True)
    filename = f"mobile_{file_id[:8]}.jpg"
    rel_path = f"{date_dir}/{filename}"
    (UPLOADS_DIR / rel_path).write_bytes(contents)

    record = UploadRecord(file_id=file_id, original_name=filename, file_path=rel_path,
        file_size=len(contents), mime_type="image/jpeg", uploader_id=1, status="processing")
    db.add(record); db.commit()

    # 后台同步OCR处理
    def do_ocr():
        from ..database import SessionLocal
        from ..services.ocr_service import OCRService
        bg = SessionLocal()
        try:
            up = bg.query(UploadRecord).filter(UploadRecord.file_id == file_id).first()
            if up:
                r = OCRService.recognize(str(UPLOADS_DIR / up.file_path))
                ocr = OCRResult(file_id=file_id,
                    raw_text=r.get("raw_text",""),
                    receiver_name=r.get("fields",{}).get("receiver_name",""),
                    phone=r.get("fields",{}).get("phone",""),
                    province=r.get("fields",{}).get("province",""),
                    city=r.get("fields",{}).get("city",""),
                    district=r.get("fields",{}).get("district",""),
                    detail_address=r.get("fields",{}).get("detail_address",""),
                    tracking_number=r.get("fields",{}).get("tracking_number",""),
                    processing_time_ms=r.get("processing_time_ms",0),
                    status=r.get("status","manual_required"))
                bg.add(ocr); bg.commit()
                # 条码解码
                try:
                    from ..services.barcode_service import BarcodeService
                    from ..models.barcode import BarcodeResult as BR
                    br_res = BarcodeService.decode(str(UPLOADS_DIR / up.file_path))
                    bcs = br_res.get("barcodes", [])
                    if bcs:
                        fst = bcs[0]
                        bg.add(BR(file_id=file_id, barcode_type=fst["type"], barcode_data=fst["data"],
                            rect_x=fst["rect"]["x"], rect_y=fst["rect"]["y"],
                            rect_w=fst["rect"]["w"], rect_h=fst["rect"]["h"],
                            total_count=br_res["total_count"], fusion_result=br_res["fusion_result"]))
                        bg.commit()
                except: pass
                SortRuleEngine.decide(file_id, bg)
        except Exception:
            bg.rollback()
        finally:
            bg.close()
    background_tasks.add_task(do_ocr)

    return {"code": 200, "message": "上传成功", "data": {"file_id": file_id, "file_size": len(contents)}}


@device_router.get("/upload-file/{file_id}/result")
def get_mobile_result(file_id: str, db: Session = Depends(get_db)):
    """轮询查询OCR结果（仅查询DB，不执行OCR，避免阻塞）"""
    ocr_data = db.query(OCRResult).filter(OCRResult.file_id == file_id).order_by(OCRResult.created_at.desc()).first()

    if not ocr_data:
        return {"code": 200, "data": {"status": "processing"}}

    sort_data = db.query(SortingDecision).filter(SortingDecision.file_id == file_id).first()
    return {
        "code": 200, "data": {
            "status": "done",
            "ocr": {
                "receiver_name": ocr_data.receiver_name or "", "phone": ocr_data.phone or "",
                "province": ocr_data.province or "", "city": ocr_data.city or "",
                "tracking_number": ocr_data.tracking_number or "",
                "status": ocr_data.status or "",
            },
            "sort": {
                "target_chute": sort_data.target_chute if sort_data else "",
                "status": sort_data.status if sort_data else "",
            },
        },
    }


@device_router.post("/feed")
async def device_feed(
    req: DeviceFeedRequest,
    db: Session = Depends(get_db),
):
    """工业相机/扫描枪图片推送接口（预留）

    接收 Base64 编码图片 → 存盘 → 入库 → OCR识别 → 分拣 → 推送大屏
    """
    try:
        # 解码 Base64
        # 处理可能的 data:image/jpeg;base64, 前缀
        img_data = req.image_base64
        if "," in img_data and img_data.startswith("data:"):
            img_data = img_data.split(",", 1)[1]

        img_bytes = base64.b64decode(img_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Base64解码失败: {e}")

    if len(img_bytes) == 0:
        raise HTTPException(status_code=400, detail="图片数据为空")

    # 保存图片
    file_id = uuid.uuid4().hex
    now = datetime.now()
    date_dir = now.strftime("%Y-%m")
    abs_dir = UPLOADS_DIR / date_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    filename = f"device_{req.device_id}_{file_id[:8]}.jpg"
    rel_path = f"{date_dir}/{filename}"
    abs_path = UPLOADS_DIR / rel_path

    with open(abs_path, "wb") as f:
        f.write(img_bytes)

    # 入库
    record = UploadRecord(
        file_id=file_id,
        original_name=f"{req.device_id}_{now.strftime('%H%M%S')}.jpg",
        file_path=rel_path,
        thumbnail_path=None,
        file_size=len(img_bytes),
        mime_type="image/jpeg",
        uploader_id=1,
        status="done",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # 执行识别管线
    try:
        pipeline_result = await ImagePipelineService.process(file_id, db)
    except Exception as e:
        pipeline_result = {"file_id": file_id, "error": str(e)}

    # 执行分拣决策
    try:
        sort_result = SortRuleEngine.decide(file_id, db)
    except Exception as e:
        sort_result = {"file_id": file_id, "status": "failed", "reason": str(e)}

    # WebSocket 推送
    if sort_result.get("status") == "success":
        try:
            await manager.broadcast_sort_result(sort_result)
        except Exception:
            pass

    return {
        "code": 200,
        "message": "设备图片处理完成",
        "data": {
            "file_id": file_id,
            "device_id": req.device_id,
            "pipeline_result": pipeline_result,
            "sort_result": sort_result,
        },
    }
