"""异常处理路由 — 模块5破损检测 + 模块7故障告警"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..database import get_db
from ..config import UPLOADS_DIR
from ..middleware.auth_middleware import get_current_user_id
from ..models.exception import ExceptionRecord
from ..models.upload import UploadRecord
from ..services.damage_detector import DamageDetector
from ..utils.response import paginated

router = APIRouter(prefix="/api/exceptions", tags=["异常处理·破损检测"])


class CreateExceptionRequest(BaseModel):
    file_id: str
    exception_type: str = "manual"
    detail: str = ""


class ResolveRequest(BaseModel):
    action: str = "resolved"  # resolved / rerouted / discarded
    handler: str = ""
    note: str = ""
    target_chute: str = ""


@router.post("/detect/{file_id}")
def detect_damage(file_id: str, db: Session = Depends(get_db)):
    """模块5：对已上传图片执行破损检测"""
    record = db.query(UploadRecord).filter(UploadRecord.file_id == file_id).first()
    if not record:
        return {"code": 404, "message": "文件不存在"}
    image_path = str(UPLOADS_DIR / record.file_path)
    result = DamageDetector.detect(image_path)
    if result.get("damaged"):
        exc_type = result["issues"][0]["type"] if result["issues"] else "damage"
        # 防重复：检查是否已有相同类型+状态的待处理异常
        exist = db.query(ExceptionRecord).filter(
            ExceptionRecord.file_id == file_id,
            ExceptionRecord.exception_type == exc_type,
            ExceptionRecord.status == "pending"
        ).first()
        if exist:
            return {"code": 200, "data": {**result, "already_exists": True}}
        exc = ExceptionRecord(
            file_id=file_id,
            exception_type=exc_type,
            detail=str(result["issues"]),
            status="pending",
        )
        db.add(exc)
        db.commit()
    return {"code": 200, "data": result}


@router.post("")
def create_exception(req: CreateExceptionRequest, db: Session = Depends(get_db)):
    """手动创建异常记录"""
    exc = ExceptionRecord(
        file_id=req.file_id,
        exception_type=req.exception_type,
        detail=req.detail,
        status="pending",
    )
    db.add(exc)
    db.commit()
    db.refresh(exc)
    return {"code": 200, "data": {"id": exc.id, "file_id": exc.file_id, "exception_type": exc.exception_type, "status": exc.status}}


@router.get("")
def list_exceptions(page: int = 1, page_size: int = 20, chute_code: str = "", db: Session = Depends(get_db)):
    """异常工单列表（可按分拣口过滤，CH-006操作员查自己的异常）"""
    from ..models.sorting import SortingDecision

    base_query = db.query(ExceptionRecord)

    # 按分拣口过滤：查询该分拣口下的异常（通过 SortingDecision 关联）
    if chute_code:
        file_ids = db.query(SortingDecision.file_id).filter(
            SortingDecision.target_chute == chute_code
        ).subquery()
        base_query = base_query.filter(ExceptionRecord.file_id.in_(file_ids))

    total = base_query.count()
    items = base_query.order_by(ExceptionRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    # 同时查询关联的上传记录以获得图片路径
    file_ids = [e.file_id for e in items]
    uploads = {}
    if file_ids:
        records = db.query(UploadRecord).filter(UploadRecord.file_id.in_(file_ids)).all()
        uploads = {r.file_id: r.file_path for r in records}
    return paginated([
        {
            "id": e.id, "file_id": e.file_id, "exception_type": e.exception_type,
            "status": e.status, "detail": e.detail,
            "image_path": uploads.get(e.file_id, ""),
            "image_url": f"/uploads/{uploads[e.file_id]}" if uploads.get(e.file_id) else "",
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in items
    ], total, page, page_size)


@router.post("/{exc_id}/process")
def start_process(exc_id: int, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """领取异常工单，状态变为处理中"""
    exc = db.query(ExceptionRecord).get(exc_id)
    if not exc: return {"code": 404, "message": "不存在"}
    if exc.status != "pending": return {"code": 400, "message": f"当前状态为 {exc.status}，无法领取"}
    exc.status = "processing"
    exc.resolved_by = user_id
    db.commit()
    return {"code": 200, "message": "已领取，处理中", "data": {"id": exc.id, "status": exc.status}}


@router.put("/{exc_id}/resolve")
def resolve(exc_id: int, req: ResolveRequest, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """完成异常处理：直接处理(→CH-006) / 分流分拣(→指定正常口) / 标记废弃(→CH-006)"""
    from ..models.sorting import SortingDecision
    from ..models.ocr import OCRResult
    import uuid as _uuid

    exc = db.query(ExceptionRecord).get(exc_id)
    if not exc: return {"code": 404, "message": "不存在"}
    if exc.status not in ("pending", "processing"):
        return {"code": 400, "message": f"当前状态为 {exc.status}，无法完成"}

    # 【校验前置】分流分拣必须指定有效目标分拣口
    if req.action == "rerouted":
        if not req.target_chute or req.target_chute == "CH-006":
            return {"code": 400, "message": "分流分拣必须指定一个正常分拣口，不能选择异常暂存口(CH-006)"}

    # 读取真实OCR运单号
    ocr = db.query(OCRResult).filter(OCRResult.file_id == exc.file_id).order_by(OCRResult.created_at.desc()).first()
    real_tn = ocr.tracking_number if ocr and ocr.tracking_number else ""
    handler_suffix = f"({req.handler})" if req.handler else ""

    # 更新异常工单状态
    exc.status = "resolved"
    exc.resolved_by = user_id
    exc.resolution = f"[{req.action}] {req.handler}: {req.note}" if req.handler else f"[{req.action}] {req.note}"

    # 软标记旧分拣记录为 failed（被异常处理覆盖）
    db.query(SortingDecision).filter(
        SortingDecision.file_id == exc.file_id,
        SortingDecision.status.in_(["pending", "dispatched", "accepted", "processing", "completed"])
    ).update({"status": "failed"}, synchronize_session=False)

    # 创建新的分拣记录
    if req.action == "resolved":
        sd = SortingDecision(
            decision_id=_uuid.uuid4().hex, file_id=exc.file_id,
            tracking_number=real_tn or f"EXC-{exc.file_id[:8]}",
            province="江西",
            city="南昌市",
            district=f"异常{handler_suffix}" if handler_suffix else "异常",
            target_chute="CH-006", status="pending", priority=1, rule_id="R-EXC",
        )
        db.add(sd)

    elif req.action == "rerouted":
        sd = SortingDecision(
            decision_id=_uuid.uuid4().hex, file_id=exc.file_id,
            tracking_number=real_tn or f"EXC-{exc.file_id[:8]}",
            province="江西",
            city="南昌市",
            district=ocr.district if ocr and ocr.district else "",
            target_chute=req.target_chute, status="pending", priority=1, rule_id="R-EXC",
        )
        db.add(sd)

    elif req.action == "discarded":
        sd = SortingDecision(
            decision_id=_uuid.uuid4().hex, file_id=exc.file_id,
            tracking_number=real_tn or f"EXC-{exc.file_id[:8]}",
            province="江西",
            city="南昌市",
            district=f"废弃{handler_suffix}" if handler_suffix else "废弃",
            target_chute="CH-006", status="failed", priority=1, rule_id="R-EXC",
        )
        db.add(sd)

    db.commit()
    return {"code": 200, "message": "处理完成", "data": {"id": exc.id, "status": exc.status, "resolution": exc.resolution}}


@router.delete("/{exc_id}")
def delete_exception(exc_id: int, db: Session = Depends(get_db)):
    """删除异常记录"""
    exc = db.query(ExceptionRecord).get(exc_id)
    if not exc: return {"code": 404, "message": "不存在"}
    db.delete(exc)
    db.commit()
    return {"code": 200, "message": "已删除"}
