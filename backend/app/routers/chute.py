"""分拣口管理 — F08"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.sorting import SortingChute, SortingDecision, SortingRule
from ..models.ocr import OCRResult
from ..models.upload import UploadRecord

router = APIRouter(prefix="/api/chutes", tags=["分拣口管理"])


class ManualSortRequest(BaseModel):
    district: str = ""
    province: str = ""
    city: str = ""
    receiver_name: str = ""
    phone: str = ""


@router.get("/packages/detail/{tracking_number}")
def package_detail(tracking_number: str, db: Session = Depends(get_db)):
    """获取包裹详情（含图片和OCR信息），用于人工复核"""
    decision = db.query(SortingDecision).filter(
        SortingDecision.tracking_number == tracking_number
    ).first()
    if not decision:
        return {"code": 404, "message": "包裹不存在"}

    upload = db.query(UploadRecord).filter(
        UploadRecord.file_id == decision.file_id
    ).first()

    ocr = db.query(OCRResult).filter(
        OCRResult.file_id == decision.file_id
    ).order_by(OCRResult.created_at.desc()).first()

    return {
        "code": 200,
        "data": {
            "tracking_number": decision.tracking_number,
            "file_id": decision.file_id,
            "province": decision.district or decision.province,
            "city": decision.city,
            "target_chute": decision.target_chute,
            "status": decision.status,
            "image_url": f"/uploads/{upload.file_path}" if upload and upload.file_path else "",
            "ocr_text": ocr.raw_text if ocr else "",
            "ocr_province": ocr.district or ocr.province if ocr else "",
            "ocr_city": ocr.city if ocr else "",
        },
    }


@router.post("/packages/{tracking_number}/manual-sort")
def manual_sort(tracking_number: str, req: ManualSortRequest, db: Session = Depends(get_db)):
    """人工填写省份城市，重新分拣到正确分拣口"""
    # 匹配分拣规则：优先按 district 匹配，fallback 到 province
    rule = None
    if req.district:
        rule = db.query(SortingRule).filter(SortingRule.district == req.district).first()
    if not rule and req.province:
        rule = db.query(SortingRule).filter(SortingRule.province == req.province).first()
    target = rule.target_chute if rule else None

    # 更新分拣记录
    decision = db.query(SortingDecision).filter(
        SortingDecision.tracking_number == tracking_number
    ).first()
    if not decision:
        return {"code": 404, "message": "包裹不存在"}

    decision.province = "江西"
    decision.city = "南昌市"
    decision.district = req.district or req.province or ""
    decision.target_chute = target or "CH-006"
    decision.status = "pending" if target else "pending"
    db.commit()

    return {
        "code": 200,
        "message": "人工分拣完成" if target else "无匹配规则，保留在异常暂存口",
        "data": {"target_chute": decision.target_chute, "status": decision.status},
    }


@router.post("/packages/{tracking_number}/discard")
def discard_package(tracking_number: str, db: Session = Depends(get_db)):
    """丢弃包裹（从分拣口移除）"""
    db.query(SortingDecision).filter(
        SortingDecision.tracking_number == tracking_number
    ).delete()
    db.commit()
    return {"code": 200, "message": "包裹已丢弃"}


@router.get("/{chute_code}/packages")
def chute_packages(chute_code: str, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    """查看某分拣口下的包裹列表"""
    total = db.query(SortingDecision).filter(SortingDecision.target_chute == chute_code).count()
    decisions = (
        db.query(SortingDecision)
        .filter(SortingDecision.target_chute == chute_code)
        .order_by(SortingDecision.decision_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # 关联查询 OCR 结果获取完整字段
    file_ids = [d.file_id for d in decisions]
    ocr_map = {}
    if file_ids:
        ocrs = db.query(OCRResult).filter(OCRResult.file_id.in_(file_ids)).all()
        ocr_map = {o.file_id: o for o in ocrs}
    items = []
    for d in decisions:
        ocr = ocr_map.get(d.file_id)
        items.append({
            "tracking_number": d.tracking_number,
            "province": d.province,
            "city": d.city,
            "target_chute": d.target_chute,
            "status": d.status,
            "ocr_status": ocr.status if ocr else None,
            "decision_time": d.decision_time.isoformat() if d.decision_time else None,
        })
    from ..utils.response import paginated
    return paginated(items, total, page, page_size)

@router.get("")
def list_chutes(db: Session = Depends(get_db)):
    chutes = db.query(SortingChute).all()
    return {"code": 200, "data": [{"id": c.id, "chute_code": c.chute_code, "name": c.name, "location": c.location, "capacity": c.capacity, "is_active": c.is_active, "description": c.description} for c in chutes]}

@router.post("")
def create_chute(data: dict, db: Session = Depends(get_db)):
    if db.query(SortingChute).filter(SortingChute.chute_code == data["chute_code"]).first():
        raise HTTPException(400, "编码已存在")
    c = SortingChute(**data); db.add(c); db.commit(); db.refresh(c)
    return {"code": 200, "message": "创建成功", "data": {"id": c.id}}

@router.put("/{chute_id}")
def update_chute(chute_id: int, data: dict, db: Session = Depends(get_db)):
    c = db.query(SortingChute).get(chute_id)
    if not c: raise HTTPException(404, "不存在")
    for k, v in data.items(): setattr(c, k, v)
    db.commit()
    return {"code": 200, "message": "更新成功"}

@router.delete("/{chute_id}")
def delete_chute(chute_id: int, db: Session = Depends(get_db)):
    c = db.query(SortingChute).get(chute_id)
    if not c: raise HTTPException(404, "不存在")
    db.delete(c); db.commit()
    return {"code": 200, "message": "已删除"}


@router.post("/packages/{tracking_number}/done")
def mark_package_done(tracking_number: str, db: Session = Depends(get_db)):
    """标记包裹已处理完成（从分拣口移除）"""
    affected = db.query(SortingDecision).filter(
        SortingDecision.tracking_number == tracking_number
    ).delete()
    db.commit()
    return {"code": 200, "message": f"已处理 {affected} 条记录"}
