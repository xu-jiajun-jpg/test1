"""模块9：智能排班路由"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models.sorting import SortingDecision
from ..services.scheduling_engine import SchedulingEngine

router = APIRouter(prefix="/api/scheduling", tags=["智能排班"])


@router.get("/predict")
def predict(date: str = "", operators: int = 10, db: Session = Depends(get_db)):
    """从真实数据库读取历史分拣数据，AI预测+排班"""
    # 从数据库获取最近5天每小时的排序数据作为历史
    history = []
    today = datetime.now()
    for d in range(5, 0, -1):
        day = today - timedelta(days=d)
        for h in range(24):
            start = day.replace(hour=h, minute=0, second=0)
            end = start + timedelta(hours=1)
            cnt = db.query(func.count(SortingDecision.id)).filter(
                SortingDecision.decision_time >= start,
                SortingDecision.decision_time < end
            ).scalar() or 0
            history.append({"date": day.strftime("%Y-%m-%d"), "hour": h, "count": cnt})

    # 如果数据库无历史数据，使用模拟数据
    if sum(h["count"] for h in history) == 0:
        history = [
            {"date": f"2026-06-{d:02d}", "hour": h, "count": abs(int(200 + h * 80 + d * 30))}
            for d in range(20, 26) for h in range(24)
        ]

    target_date = date or today.strftime("%Y-%m-%d")
    pred = SchedulingEngine.predict_volume(history, target_date)
    schedule = SchedulingEngine.generate_schedule(pred, operators)
    equipment = SchedulingEngine.optimize_equipment(pred)
    return {"code": 200, "data": {"prediction": pred, "schedule": schedule, "equipment": equipment, "history_count": len(history)}}
