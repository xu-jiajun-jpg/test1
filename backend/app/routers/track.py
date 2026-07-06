"""包裹追踪 — 模块13"""
import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.ocr import OCRResult
from ..models.sorting import SortingDecision
from ..models.upload import UploadRecord

router = APIRouter(prefix="/api/track", tags=["包裹追踪"])


def _calc_eta() -> str:
    """计算预计出仓时间：次日白天随机时间 9:00-18:00"""
    tomorrow = datetime.now() + timedelta(days=1)
    hour = random.randint(9, 17)
    minute = random.choice([0, 10, 20, 30, 40, 50])
    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M")


@router.get("/{tracking_number}")
def track(tracking_number: str, db: Session = Depends(get_db)):
    """根据运单号查询物流时间线（小程序扫码调用）"""
    ocr = db.query(OCRResult).filter(OCRResult.tracking_number == tracking_number).first()
    if not ocr:
        return {"code": 404, "message": "未找到该运单"}

    decision = db.query(SortingDecision).filter(SortingDecision.file_id == ocr.file_id).first()

    timeline = []
    upload = db.query(UploadRecord).filter(UploadRecord.file_id == ocr.file_id).first()
    if upload and upload.created_at:
        timeline.append({"time": upload.created_at.isoformat(), "desc": "📸 包裹图片已上传"})
    if ocr.created_at:
        timeline.append({"time": ocr.created_at.isoformat(), "desc": f"🔍 OCR识别完成 → {ocr.district or ocr.province or '未知'}{ocr.city or ''}"})
    if decision:
        timeline.append({"time": decision.decision_time.isoformat() if decision.decision_time else "",
                         "desc": f"📦 分拣决策 → {decision.target_chute} ({decision.status})"})

    # 分拣成功后添加预计出仓
    eta = _calc_eta() if decision and decision.status in ("completed", "verified") else ""
    if eta:
        timeline.append({"time": eta, "desc": f"🚚 预计出仓时间"})

    return {
        "code": 200,
        "data": {
            "tracking_number": tracking_number,
            "province": ocr.province,
            "city": ocr.city,
            "district": ocr.district,
            "address": ocr.detail_address,
            "phone": ocr.phone,
            "receiver_name": ocr.receiver_name,
            "eta": eta,
            "target_chute": decision.target_chute if decision else "",
            "status": decision.status if decision else "unknown",
            "timeline": timeline,
        },
    }


@router.put("/{tracking_number}/address")
def update_address(tracking_number: str, data: dict, db: Session = Depends(get_db)):
    """小程序端：修改收件地址"""
    ocr = db.query(OCRResult).filter(OCRResult.tracking_number == tracking_number).first()
    if not ocr:
        return {"code": 404, "message": "未找到该运单"}

    # 更新地址字段
    ocr.province = data.get("province", ocr.province)
    ocr.city = data.get("city", ocr.city)
    ocr.district = data.get("district", ocr.district)
    ocr.detail_address = data.get("detail_address", ocr.detail_address)
    ocr.receiver_name = data.get("receiver_name", ocr.receiver_name)
    ocr.phone = data.get("phone", ocr.phone)

    # 标记需要重新决策
    from ..services.sort_engine import SortRuleEngine
    SortRuleEngine.decide(ocr.file_id, db)

    return {
        "code": 200,
        "message": "地址变更已生效，分拣口已重新分配",
        "data": {
            "new_province": ocr.province,
            "new_city": ocr.city,
            "new_district": ocr.district,
            "updated_at": datetime.utcnow().isoformat(),
        },
    }
