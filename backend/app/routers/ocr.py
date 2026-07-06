"""OCR识别路由"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..services.image_pipeline import ImagePipelineService
from ..models.ocr import OCRResult
from ..models.upload import UploadRecord
from ..config import UPLOADS_DIR

router = APIRouter(prefix="/api/ocr", tags=["OCR识别"])


@router.post("/recognize/{file_id}")
async def recognize(
    file_id: str,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """触发图片识别管线（同步执行，引擎已预热）"""
    record = db.query(UploadRecord).filter(UploadRecord.file_id == file_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="文件不存在")
    if record.status == "processing":
        raise HTTPException(status_code=400, detail="该文件正在处理中")

    try:
        result = await ImagePipelineService.process(file_id, db)
        from ..services.sort_engine import SortRuleEngine
        SortRuleEngine.decide(file_id, db)
        return {"code": 200, "message": "识别完成", "data": result}
    except Exception as e:
        # OCR失败时返回部分结果而非500，避免前端误判
        return {"code": 200, "message": f"部分识别完成: {e}", "data": {
            "file_id": file_id,
            "ocr": {"status": "failed", "fields": {}},
            "total_time_ms": 0,
        }}


@router.get("/results/{file_id}")
def get_result(
    file_id: str,
    db: Session = Depends(get_db),
):
    """查询某文件的OCR结果"""
    ocr = db.query(OCRResult).filter(OCRResult.file_id == file_id).first()
    if not ocr:
        return {"code": 200, "data": None}

    return {
        "code": 200,
        "data": {
            "receiver_name": ocr.receiver_name,
            "phone": ocr.phone,
            "province": ocr.province,
            "city": ocr.city,
            "district": ocr.district,
            "detail_address": ocr.detail_address,
            "tracking_number": ocr.tracking_number,
            "status": ocr.status,
            "raw_text": ocr.raw_text,
            "processing_time_ms": ocr.processing_time_ms,
        },
    }


@router.get("/results")
def list_results(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """分页查询OCR结果列表"""
    total = db.query(OCRResult).count()
    results = (
        db.query(OCRResult)
        .order_by(OCRResult.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 批量获取 UploadRecord（避免 N+1）
    file_ids = [r.file_id for r in results]
    upload_map = {}
    barcode_map = {}
    if file_ids:
        uploads = db.query(UploadRecord).filter(UploadRecord.file_id.in_(file_ids)).all()
        upload_map = {u.file_id: u for u in uploads}
        # 批量获取条码结果
        from ..models.barcode import BarcodeResult
        barcodes = db.query(BarcodeResult).filter(BarcodeResult.file_id.in_(file_ids)).all()
        for b in barcodes:
            if b.file_id not in barcode_map:
                barcode_map[b.file_id] = b

    items = []
    for r in results:
        upload = upload_map.get(r.file_id)
        barcode = barcode_map.get(r.file_id)
        items.append({
            "file_id": r.file_id,
            "original_name": upload.original_name if upload else "",
            "file_url": f"/uploads/{upload.file_path}" if upload else "",
            "barcode_type": barcode.barcode_type if barcode else None,
            "barcode_data": barcode.barcode_data if barcode else None,
            "thumbnail_url": f"/uploads/{upload.thumbnail_path}" if upload and upload.thumbnail_path else None,
            "tracking_number": r.tracking_number,
            "province": r.province,
            "city": r.city,
            "district": r.district or "",
            "status": r.status,
            "processing_time_ms": r.processing_time_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    from ..utils.response import paginated
    return paginated(items, total, page, page_size)
