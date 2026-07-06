"""SLA超时配置模型 — 按分拣口维度的时效阈值"""
from sqlalchemy import Column, Integer, String, Boolean
from ..database import Base
from .base import TimestampMixin


class SlaConfig(Base, TimestampMixin):
    __tablename__ = "sla_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chute_code = Column(String(50), unique=True, nullable=False, index=True, comment="分拣口编码")
    chute_name = Column(String(100), comment="分拣口名称")
    # 超时阈值（分钟）：接收超时 / 执行超时
    accept_timeout = Column(Integer, default=10, comment="接收超时（分钟），从派发到接收的时限")
    process_timeout = Column(Integer, default=30, comment="执行超时（分钟），从接收到完成的时限")
    severity = Column(String(16), default="warning", comment="超时严重程度: info/warning/critical")
    escalation_action = Column(String(32), default="notify_admin", comment="升级动作: notify_admin/reassign/auto_escalate")
    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(String(200), comment="备注说明")
