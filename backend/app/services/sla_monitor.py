"""SLA监控后台协程 — 每30秒扫描超时任务，触发滞留告警"""
import asyncio
from datetime import datetime


async def sla_monitor_loop():
    """SLA监控循环：每30秒扫描超时未处理任务并触发task_stale事件"""
    await asyncio.sleep(20)  # 启动后等待20秒

    while True:
        try:
            from ..database import SessionLocal
            from ..models.sorting import SortingDecision
            from ..models.sla_config import SlaConfig
            from ..models.task_assignment import TaskAssignment
            from ..models.message import MessageRecord
            from ..websocket.manager import manager as ws_manager
            from sqlalchemy import func
            import uuid as _uuid

            db = SessionLocal()
            now = datetime.utcnow()

            # 1. 查询所有已派发/已接收但未完成的决策
            active_decisions = db.query(SortingDecision).filter(
                SortingDecision.status.in_(["dispatched", "accepted", "processing"]),
            ).all()

            stale_count = 0
            for decision in active_decisions:
                # 查询分拣口的SLA配置
                sla = db.query(SlaConfig).filter(
                    SlaConfig.chute_code == decision.target_chute,
                    SlaConfig.is_active == True,
                ).first()

                if not sla:
                    # 使用默认值
                    accept_timeout = 10  # 分钟
                    process_timeout = 30
                else:
                    accept_timeout = sla.accept_timeout
                    process_timeout = sla.process_timeout

                # 计算超时阈值
                timeout_minutes = accept_timeout if decision.status == "dispatched" else process_timeout

                # 以decision_time为基准
                if decision.decision_time:
                    elapsed = (now - decision.decision_time).total_seconds() / 60
                    if elapsed > timeout_minutes and decision.status != "stale":
                        # 标记为超时滞留
                        decision.status = "stale"
                        decision.escalated_at = now
                        stale_count += 1

                        # 查询操作员
                        assignment = db.query(TaskAssignment).filter(
                            TaskAssignment.decision_id == decision.decision_id,
                        ).order_by(TaskAssignment.assigned_at.desc()).first()
                        operator_id = assignment.operator_id if assignment else None

                        # 检查是否已有该任务的超时消息，避免重复创建
                        existing_msg = db.query(MessageRecord).filter(
                            MessageRecord.category == "task_stale",
                            MessageRecord.related_decision_id == decision.decision_id,
                        ).first()
                        if not existing_msg:
                            # 写入消息（管理员端）
                            msg = MessageRecord(
                                message_id=_uuid.uuid4().hex,
                                category="task_stale",
                                title=f"⚠️ 任务超时滞留",
                                content=f"包裹 {decision.tracking_number or decision.file_id[:8]} 在{decision.target_chute}超时{int(elapsed)}分钟",
                                level="warning",
                                target_role="admin",
                                from_name="系统(SLA)",
                                from_role="system",
                                related_tracking=decision.tracking_number,
                                related_chute=decision.target_chute,
                                related_decision_id=decision.decision_id,
                            )
                            db.add(msg)

                        # WebSocket推送
                        asyncio.ensure_future(
                            ws_manager.broadcast_task_stale(
                                decision.decision_id,
                                decision.target_chute or "",
                                int(elapsed),
                            )
                        )

            db.commit()
            db.close()

            if stale_count:
                print(f"[SLA Monitor] 标记 {stale_count} 个任务为超时滞留")

        except Exception as e:
            print(f"[SLA Monitor] 错误: {e}")

        await asyncio.sleep(30)
