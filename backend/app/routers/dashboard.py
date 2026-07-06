"""实时大屏路由 + WebSocket端点"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..websocket.manager import manager
from ..models.sorting import SortingDecision
from ..models.upload import UploadRecord
from ..models.ocr import OCRResult
from ..models.exception import ExceptionRecord

router = APIRouter(tags=["实时大屏"])


@router.get("/api/stats/summary")
def get_summary(db: Session = Depends(get_db)):
    """累计统计摘要"""
    total_uploaded = db.query(func.count(UploadRecord.id)).scalar() or 0
    total_ocr = db.query(func.count(OCRResult.id)).scalar() or 0
    total_decisions = db.query(func.count(SortingDecision.id)).scalar() or 0
    success_count = (
        db.query(func.count(SortingDecision.id))
        .filter(SortingDecision.status.in_(["completed", "verified"]))
        .scalar() or 0
    )
    fail_count = (
        db.query(func.count(SortingDecision.id))
        .filter(SortingDecision.status.in_(["failed", "rejected", "stale"]))
        .scalar() or 0
    )
    # 破损/异常记录中未处理的（与分拣决策表独立）
    exception_count = (
        db.query(func.count(ExceptionRecord.id))
        .filter(ExceptionRecord.status.in_(["pending", "processing"]))
        .scalar() or 0
    )

    # 各分拣口统计
    chute_stats = (
        db.query(
            SortingDecision.target_chute,
            func.count(SortingDecision.id).label("cnt"),
        )
        .filter(SortingDecision.status.in_(["completed", "verified"]))
        .group_by(SortingDecision.target_chute)
        .all()
    )

    # OEE计算
    quality_rate = round(success_count / total_decisions * 100, 1) if total_decisions > 0 else 100
    chute_count = len([c for c in chute_stats if c[0]])
    availability = round(min(chute_count / max(6, chute_count), 1.0) * 100, 1)
    utilization = round(total_ocr / max(total_uploaded, 1) * 100, 1)
    oee = round(quality_rate * availability * utilization / 10000, 1)

    # 峰谷分析（按小时统计分拣量）
    peak_valley = (
        db.query(
            func.hour(SortingDecision.decision_time).label("h"),
            func.count(SortingDecision.id).label("cnt"),
        )
        .filter(SortingDecision.decision_time != None)
        .group_by(func.hour(SortingDecision.decision_time))
        .all()
    )
    peak_data = [{"hour": h or 0, "count": c} for h, c in peak_valley]

    return {
        "code": 200,
        "data": {
            "total_uploaded": total_uploaded,
            "total_ocr": total_ocr,
            "total_decisions": total_decisions,
            "success_count": success_count,
            "fail_count": fail_count,
            "exception_count": exception_count,
            "oee": oee,
            "quality_rate": quality_rate,
            "availability": availability,
            "utilization": utilization,
            "peak_valley": peak_data,
            "chute_stats": [
                {"chute": c[0] or "其他", "count": c[1]}
                for c in chute_stats
                if c[0]
            ],
        },
    }


@router.get("/api/stats/report")
def get_report(period: str = "daily", db: Session = Depends(get_db)):
    """日报/周报/月报数据"""
    from datetime import datetime as dt
    summary = get_summary(db=db)["data"]

    # 根据period调整统计时间范围
    report = {
        "title": {"daily": "日报", "weekly": "周报", "monthly": "月报"}.get(period, "日报"),
        "generated_at": dt.now().strftime("%Y-%m-%d %H:%M"),
        "summary": summary,
        "insights": [],
    }

    # 自动生成分析洞察
    if summary["quality_rate"] < 95:
        report["insights"].append(f"⚠️ 分拣质量率{summary['quality_rate']}%，低于95%目标，需关注分拣失败原因")
    if summary["oee"] < 80:
        report["insights"].append(f"⚠️ OEE仅{summary['oee']}%，建议优化设备利用率和分拣效率")
    if summary["exception_count"] > 5:
        report["insights"].append(f"📋 待处理异常{summary['exception_count']}个，建议及时分流处理")
    if not report["insights"]:
        report["insights"].append("✅ 系统运行正常，各项指标达标")

    return {"code": 200, "data": report}


@router.get("/api/stats/recent")
def get_recent(db: Session = Depends(get_db)):
    """最近20条分拣决策"""
    decisions = (
        db.query(SortingDecision)
        .order_by(SortingDecision.decision_time.desc())
        .limit(20)
        .all()
    )
    return {
        "code": 200,
        "data": [
            {
                "tracking_number": d.tracking_number,
                "province": d.district or d.province,
                "city": d.city,
                "target_chute": d.target_chute,
                "status": d.status,
                "decision_time": d.decision_time.isoformat() if d.decision_time else None,
            }
            for d in decisions
        ],
    }


@router.get("/api/stats/history")
def get_history(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """历史统计查询（与 F06 共享）"""
    total = db.query(SortingDecision).count()
    decisions = (
        db.query(SortingDecision)
        .order_by(SortingDecision.decision_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    from ..utils.response import paginated
    items = [
        {
            "tracking_number": d.tracking_number,
            "province": d.district or d.province,
            "city": d.city,
            "target_chute": d.target_chute,
            "status": d.status,
            "decision_time": d.decision_time.isoformat() if d.decision_time else None,
        }
        for d in decisions
    ]
    return paginated(items, total, page, page_size)


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket, token: str = Query(None)):
    """实时大屏 WebSocket 连接"""
    await manager.connect(websocket, "dashboard")
    try:
        # 发送初始连接确认
        await websocket.send_json({"event": "connected", "message": "已连接"})
        while True:
            # 保持连接，等待客户端消息（心跳用）
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "dashboard")
