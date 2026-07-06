"""任务监控路由 — 管理员端：状态聚合 / 超时列表 / 操作员负载 / SLA配置"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case, text
from pydantic import BaseModel

from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..models.sorting import SortingDecision
from ..models.operator import Operator, OperatorChute
from ..models.task_assignment import TaskAssignment
from ..models.sla_config import SlaConfig

router = APIRouter(prefix="/api/tasks", tags=["任务监控·SLA配置"])


# ===== 1. 任务状态聚合快照 =====
@router.get("/status-summary")
def task_status_summary(db: Session = Depends(get_db)):
    """获取各状态任务数量汇总"""
    counts = db.query(
        SortingDecision.status,
        func.count(SortingDecision.id).label("count"),
    ).group_by(SortingDecision.status).all()

    status_map = {row.status: row.count for row in counts}

    # 统计各操作员的当前负载
    operator_load = db.query(
        TaskAssignment.operator_id,
        func.count(TaskAssignment.id).label("task_count"),
    ).filter(
        TaskAssignment.status.in_(["dispatched", "accepted", "processing"]),
    ).group_by(TaskAssignment.operator_id).all()

    # 超时任务统计
    now = datetime.utcnow()
    stale_count = db.query(SortingDecision).filter(
        SortingDecision.status == "stale"
    ).count()

    return {
        "code": 200,
        "data": {
            "status_counts": {
                "pending": status_map.get("pending", 0),
                "dispatched": status_map.get("dispatched", 0),
                "accepted": status_map.get("accepted", 0),
                "processing": status_map.get("processing", 0),
                "completed": status_map.get("completed", 0),
                "verified": status_map.get("verified", 0),
                "rejected": status_map.get("rejected", 0),
                "stale": stale_count,
                "failed": status_map.get("failed", 0),
            },
            "operator_load": [
                {"operator_id": oid, "active_tasks": cnt}
                for oid, cnt in operator_load
            ],
            "total": sum(status_map.values()),
        },
    }


# ===== 2. 操作员负载详情 =====
@router.get("/operator-workload")
def operator_workload(db: Session = Depends(get_db)):
    """获取每个操作员的当前负载和统计"""
    operators = db.query(Operator).filter(Operator.status == "active").all()
    result = []

    for op in operators:
        # 查询该操作员的活跃任务
        active_tasks = db.query(TaskAssignment).filter(
            TaskAssignment.operator_id == op.id,
            TaskAssignment.status.in_(["dispatched", "accepted", "processing"]),
        ).count()

        # 今日完成数
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_completed = db.query(TaskAssignment).filter(
            TaskAssignment.operator_id == op.id,
            TaskAssignment.status == "completed",
            TaskAssignment.completed_at >= today,
        ).count()

        # 超时任务数
        stale_tasks = db.query(
            SortingDecision, TaskAssignment
        ).join(
            TaskAssignment,
            SortingDecision.decision_id == TaskAssignment.decision_id,
        ).filter(
            TaskAssignment.operator_id == op.id,
            SortingDecision.status == "stale",
        ).count()

        chutes = db.query(OperatorChute).filter(OperatorChute.operator_id == op.id).all()

        result.append({
            "operator_id": op.id,
            "name": op.name,
            "shift": op.shift,
            "status": op.status,
            "chutes": [c.chute_code for c in chutes],
            "active_tasks": active_tasks,
            "today_completed": today_completed,
            "stale_tasks": stale_tasks,
        })

    return {"code": 200, "data": result}


# ===== 3. 超时/滞留任务列表 =====
@router.get("/stale-tasks")
def stale_tasks(db: Session = Depends(get_db)):
    """获取所有超时滞留任务"""
    decisions = db.query(SortingDecision).filter(
        SortingDecision.status == "stale",
    ).order_by(SortingDecision.escalated_at.desc().nullslast()).limit(50).all()

    # 关联派发记录查询操作员
    task_list = []
    for d in decisions:
        assignment = db.query(TaskAssignment).filter(
            TaskAssignment.decision_id == d.decision_id,
        ).order_by(TaskAssignment.assigned_at.desc()).first()

        overdue_minutes = 0
        if d.escalated_at:
            overdue_minutes = int((datetime.utcnow() - d.escalated_at).total_seconds() / 60)

        task_list.append({
            "decision_id": d.decision_id,
            "file_id": d.file_id,
            "tracking_number": d.tracking_number or "",
            "target_chute": d.target_chute or "",
            "operator_name": assignment.operator_name if assignment else "",
            "operator_id": assignment.operator_id if assignment else None,
            "escalated_at": d.escalated_at.isoformat() if d.escalated_at else None,
            "overdue_minutes": overdue_minutes,
            "urge_count": d.urge_count or 0,
            "decision_time": d.decision_time.isoformat() if d.decision_time else None,
        })

    return {"code": 200, "data": {"tasks": task_list, "total": len(task_list)}}


# ===== 4. 按操作员/分拣口/状态查询任务明细 =====
@router.get("/task-list")
def task_list(
    operator_id: int = None,
    chute_code: str = None,
    status: str = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """多维查询任务列表"""
    query = db.query(SortingDecision)

    if status:
        query = query.filter(SortingDecision.status == status)
    if chute_code:
        query = query.filter(SortingDecision.target_chute == chute_code)
    if operator_id:
        query = query.join(
            TaskAssignment,
            SortingDecision.decision_id == TaskAssignment.decision_id,
        ).filter(TaskAssignment.operator_id == operator_id)

    total = query.count()
    items = query.order_by(SortingDecision.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    result = []
    for d in items:
        assignment = db.query(TaskAssignment).filter(
            TaskAssignment.decision_id == d.decision_id,
        ).order_by(TaskAssignment.assigned_at.desc()).first()

        result.append({
            "decision_id": d.decision_id,
            "file_id": d.file_id,
            "tracking_number": d.tracking_number or "",
            "province": d.province or "",
            "city": d.city or "",
            "district": d.district or "",
            "target_chute": d.target_chute or "",
            "status": d.status,
            "operator_name": assignment.operator_name if assignment else "",
            "operator_id": assignment.operator_id if assignment else None,
            "decision_time": d.decision_time.isoformat() if d.decision_time else None,
            "handled_at": d.handled_at.isoformat() if d.handled_at else None,
            "urge_count": d.urge_count or 0,
            "sla_deadline": d.sla_deadline.isoformat() if d.sla_deadline else None,
        })

    from ..utils.response import paginated
    return paginated(result, total, page, page_size)
