"""条码识别路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.barcode import BarcodeResult

router = APIRouter(prefix="/api/barcode", tags=["条码识别"])


@router.get("/results/{file_id}")
def get_barcode_result(
    file_id: str,
    db: Session = Depends(get_db),
):
    """查询某文件的条码结果"""
    barcode = db.query(BarcodeResult).filter(BarcodeResult.file_id == file_id).first()
    if not barcode:
        return {"code": 200, "data": None}

    return {
        "code": 200,
        "data": {
            "barcode_type": barcode.barcode_type,
            "barcode_data": barcode.barcode_data,
            "total_count": barcode.total_count,
            "fusion_result": barcode.fusion_result,
        },
    }
