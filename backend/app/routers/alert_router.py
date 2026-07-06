"""告警管理 — F13"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models.alert import AlertRule, AlertHistory
from ..models.sorting import SortingDecision
from ..models.exception import ExceptionRecord
from ..utils.response import paginated

router = APIRouter(prefix="/api/alerts", tags=["告警管理"])


def _get_current_metrics(db: Session) -> dict:
    """获取当前系统监控指标值"""
    total = db.query(func.count(SortingDecision.id)).scalar() or 0
    fail = db.query(func.count(SortingDecision.id)).filter(
        SortingDecision.status.in_(["failed", "rejected", "stale"])
    ).scalar() or 0
    exceptions = db.query(func.count(ExceptionRecord.id)).filter(
        ExceptionRecord.status == "pending"
    ).scalar() or 0
    fail_rate = round(fail / total * 100, 1) if total > 0 else 0
    return {
        "total_sortings": total,
        "fail_count": fail,
        "fail_rate": fail_rate,
        "pending_exceptions": exceptions,
    }


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    items = db.query(AlertRule).all()
    return {"code": 200, "data": [{"id": r.id, "rule_name": r.rule_name, "metric": r.metric, "threshold": r.threshold, "alert_level": r.alert_level, "is_active": r.is_active, "cooldown_minutes": r.cooldown_minutes} for r in items]}

@router.post("/rules")
def create_rule(data: dict, db: Session = Depends(get_db)):
    r = AlertRule(**data); db.add(r); db.commit()
    return {"code": 200, "message": "规则创建成功", "data": {"id": r.id}}

@router.put("/rules/{rule_id}")
def toggle_rule(rule_id: int, data: dict, db: Session = Depends(get_db)):
    r = db.query(AlertRule).get(rule_id)
    if r: r.is_active = data.get("is_active", True); db.commit()
    return {"code": 200}

@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    r = db.query(AlertRule).get(rule_id)
    if r: db.delete(r); db.commit()
    return {"code": 200, "message": "规则已删除"}

def check_alerts_internal(db: Session) -> list:
    """内部函数：检查告警规则并生成记录，返回触发的告警列表"""
    metrics = _get_current_metrics(db)
    rules = db.query(AlertRule).filter(AlertRule.is_active == True).all()
    triggered = []

    for rule in rules:
        current_val = metrics.get(rule.metric)
        if current_val is None or current_val < rule.threshold:
            continue

        if rule.cooldown_minutes and rule.cooldown_minutes > 0:
            cooldown_time = datetime.now() - timedelta(minutes=rule.cooldown_minutes)
            recent = db.query(AlertHistory).filter(
                AlertHistory.rule_id == rule.id,
                AlertHistory.created_at > cooldown_time,
                AlertHistory.status == "triggered",
            ).first()
            if recent:
                continue

        alert = AlertHistory(
            rule_id=rule.id, metric=rule.metric,
            current_value=current_val, threshold=rule.threshold,
            alert_level=rule.alert_level,
            message=f"{rule.rule_name}: 当前值={current_val} 超过阈值={rule.threshold}",
            status="triggered",
        )
        db.add(alert)
        triggered.append({
            "rule": rule.rule_name, "metric": rule.metric,
            "current_value": current_val, "threshold": rule.threshold,
            "level": rule.alert_level, "message": alert.message,
        })

    db.commit()
    return triggered


@router.post("/check")
def check_alerts(db: Session = Depends(get_db)):
    """自动检查告警规则并生成告警记录"""
    triggered = check_alerts_internal(db)
    return {"code": 200, "data": {"metrics": _get_current_metrics(db), "triggered": triggered}}

@router.get("/history")
def list_history(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    total = db.query(AlertHistory).count()
    items = db.query(AlertHistory).order_by(AlertHistory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return paginated([{"id": h.id, "metric": h.metric, "current_value": h.current_value, "threshold": h.threshold, "alert_level": h.alert_level, "message": h.message, "status": h.status, "created_at": h.created_at.isoformat() if h.created_at else None} for h in items], total, page, page_size)
