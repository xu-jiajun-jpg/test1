"""告警规则与历史模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, Enum as SAEnum
from ..database import Base
from .base import TimestampMixin


class AlertRule(Base, TimestampMixin):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(100), nullable=False, comment="规则名称")
    metric = Column(String(50), nullable=False, comment="监控指标")
    threshold = Column(Float, nullable=False, comment="阈值")
    alert_level = Column(String(16), default="warning", comment="告警等级: info/warning/critical")
    cooldown_minutes = Column(Integer, default=30, comment="冷却期(分钟)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(String(200), comment="规则描述")


class AlertHistory(Base, TimestampMixin):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(Integer, comment="触发规则ID")
    metric = Column(String(50), comment="触发指标")
    current_value = Column(Float, comment="当前值")
    threshold = Column(Float, comment="阈值")
    alert_level = Column(String(16), comment="告警等级")
    message = Column(String(500), comment="告警消息")
    status = Column(
        SAEnum("triggered", "acknowledged", "resolved", name="alert_status"),
        default="triggered",
        comment="告警状态",
    )
    acknowledged_by = Column(Integer, comment="确认人ID")
