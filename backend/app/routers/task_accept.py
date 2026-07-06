"""任务接收路由 — 操作员接收/拒收/执行/完成/异常上报"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import uuid as _uuid

from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..models.sorting import SortingDecision
from ..models.operator import Operator, OperatorChute
from ..models.task_assignment import TaskAssignment
from ..models.exception import ExceptionRecord
from ..models.message import MessageRecord
from ..websocket.manager import manager as ws_manager

router = APIRouter(prefix="/api/tasks", tags=["任务接收·执行反馈"])


def _get_operator(db: Session, user_id: int):
    """获取当前用户关联的操作员 — 优先使用 operator_id 直连"""
    from ..models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    if user.operator_id:
        return db.query(Operator).filter(Operator.id == user.operator_id).first()
    return db.query(Operator).filter(
        (Operator.name == user.display_name) | (func.instr(user.display_name, Operator.name) > 0)
    ).first()


# ===== 请求模型 =====
class AcceptRequest(BaseModel):
    decision_id: str

class RejectRequest(BaseModel):
    decision_id: str
    reason: str = ""

class StartProcessingRequest(BaseModel):
    decision_id: str

class CompleteRequest(BaseModel):
    decision_id: str
    target_chute: str = ""  # 非空则分流到指定口

class VerifyRequest(BaseModel):
    decision_id: str


# ===== 1. 操作员接收任务 =====
@router.post("/accept")
async def accept_task(
    req: AcceptRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """操作员确认接收任务"""
    operator = _get_operator(db, user_id)
    if not operator:
        raise HTTPException(400, "未找到操作员信息")

    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "任务不存在")

    # 状态校验：只有dispatched可以接收
    if decision.status != "dispatched" and decision.status != "stale":
        return {"code": 400, "message": f"当前状态为{decision.status}，无法接收"}

    old_status = decision.status
    decision.status = "accepted"
    now = datetime.utcnow()

    # 更新派发记录
    assignment = db.query(TaskAssignment).filter(
        TaskAssignment.decision_id == req.decision_id,
        TaskAssignment.operator_id == operator.id,
    ).order_by(TaskAssignment.assigned_at.desc()).first()
    if assignment:
        assignment.status = "accepted"
        assignment.accepted_at = now

    db.commit()

    # WebSocket推送
    background_tasks.add_task(ws_manager.notify_task_accepted, operator.id, req.decision_id)

    return {"code": 200, "message": "已接收任务", "data": {
        "decision_id": req.decision_id,
        "tracking_number": decision.tracking_number,
        "target_chute": decision.target_chute,
    }}


# ===== 2. 操作员拒收任务 =====
@router.post("/reject")
async def reject_task(
    req: RejectRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """操作员拒收任务"""
    operator = _get_operator(db, user_id)
    if not operator:
        raise HTTPException(400, "未找到操作员信息")

    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "任务不存在")

    if decision.status not in ("dispatched", "accepted"):
        return {"code": 400, "message": f"当前状态为{decision.status}，无法拒收"}

    decision.status = "rejected"

    # 更新派发记录
    assignment = db.query(TaskAssignment).filter(
        TaskAssignment.decision_id == req.decision_id,
        TaskAssignment.operator_id == operator.id,
    ).order_by(TaskAssignment.assigned_at.desc()).first()
    if assignment:
        assignment.status = "rejected"
        assignment.reject_reason = req.reason

    # 创建异常记录（拒收作为异常类型）
    exc = ExceptionRecord(
        exception_id=_uuid.uuid4().hex,
        file_id=decision.file_id,
        tracking_number=decision.tracking_number or "",
        exception_type="operator_rejection",
        description=f"操作员拒收: {req.reason or '未说明原因'}",
        severity="medium",
        status="open",
        reported_by=operator.name,
        reported_at=datetime.utcnow(),
        related_decision_id=decision.decision_id,
    )
    db.add(exc)

    # 写入消息（管理员端可见）
    msg = MessageRecord(
        message_id=_uuid.uuid4().hex,
        category="task_rejected",
        title=f"⛔ {operator.name} 拒收任务",
        content=f"包裹 {decision.tracking_number or decision.file_id[:8]} → {decision.target_chute}，原因: {req.reason or '未说明'}",
        level="warning",
        target_role="admin",
        from_name=operator.name,
        from_role="operator",
        related_tracking=decision.tracking_number,
        related_chute=decision.target_chute,
        related_decision_id=decision.decision_id,
    )
    db.add(msg)
    db.commit()

    background_tasks.add_task(
        ws_manager.notify_task_rejected, operator.id, req.decision_id, req.reason or ""
    )

    return {"code": 200, "message": "已拒收", "data": {
        "decision_id": req.decision_id,
        "reason": req.reason,
    }}


# ===== 3. 操作员开始执行 =====
@router.post("/start")
async def start_processing(
    req: StartProcessingRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """操作员开始执行分拣操作"""
    operator = _get_operator(db, user_id)
    if not operator:
        raise HTTPException(400, "未找到操作员信息")

    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "任务不存在")

    if decision.status != "accepted":
        return {"code": 400, "message": f"当前状态为{decision.status}，需先接收才能开始执行"}

    decision.status = "processing"
    db.commit()

    background_tasks.add_task(ws_manager.broadcast_task_processing, operator.id, req.decision_id)

    return {"code": 200, "message": "开始执行", "data": {"decision_id": req.decision_id}}


# ===== 4. 操作员完成任务 =====
@router.post("/complete")
async def complete_task(
    req: CompleteRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """操作员确认分拣完成（支持分流到不同分拣口）"""
    operator = _get_operator(db, user_id)
    if not operator:
        raise HTTPException(400, "未找到操作员信息")

    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "任务不存在")

    if decision.status not in ("processing", "accepted"):
        return {"code": 400, "message": f"当前状态为{decision.status}，无法标记完成"}

    now = datetime.utcnow()

    # 如果指定了新的分拣口（分流）
    new_chute = req.target_chute.strip() if req.target_chute else ""
    target_chute = new_chute if new_chute else (decision.target_chute or "")

    if new_chute and new_chute != decision.target_chute and new_chute != "CH-006":
        # 创建新的分拣记录（分流）
        new_decision = SortingDecision(
            decision_id=_uuid.uuid4().hex,
            file_id=decision.file_id,
            tracking_number=decision.tracking_number,
            province=decision.province,
            city=decision.city,
            district=decision.district,
            target_chute=new_chute,
            status="completed",
            priority=decision.priority or 1,
            rule_id="R-OP",
            decision_time=now,
            handled_at=now,
            handled_by=operator.id,
        )
        db.add(new_decision)
        decision.status = "completed"
    else:
        decision.status = "completed"
        target_chute = decision.target_chute or ""

    decision.handled_at = now
    decision.handled_by = operator.id

    # 更新派发记录
    assignment = db.query(TaskAssignment).filter(
        TaskAssignment.decision_id == req.decision_id,
        TaskAssignment.operator_id == operator.id,
    ).order_by(TaskAssignment.assigned_at.desc()).first()
    if assignment:
        assignment.status = "completed"
        assignment.completed_at = now

    db.commit()

    background_tasks.add_task(
        ws_manager.broadcast_task_completed,
        operator.id, req.decision_id, decision.tracking_number or "", target_chute,
    )

    return {"code": 200, "message": "分拣完成", "data": {
        "decision_id": req.decision_id,
        "tracking_number": decision.tracking_number,
        "target_chute": target_chute,
    }}


# ===== 5. 管理员核验 =====
@router.post("/verify")
async def verify_task(
    req: VerifyRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """管理员核验已完成的分拣任务"""
    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "任务不存在")

    if decision.status != "completed":
        return {"code": 400, "message": f"当前状态为{decision.status}，无法核验"}

    decision.status = "verified"
    db.commit()

    # 通知操作员
    background_tasks.add_task(
        ws_manager.broadcast_task_verified, req.decision_id, "管理员"
    )

    return {"code": 200, "message": "核验通过", "data": {"decision_id": req.decision_id}}
