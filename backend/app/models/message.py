"""消息记录模型 — 管理员↔操作员协同消息"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from ..database import Base
from .base import TimestampMixin


class MessageRecord(Base, TimestampMixin):
    __tablename__ = "message_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(36), unique=True, nullable=False, index=True, comment="消息唯一ID")
    category = Column(String(32), nullable=False, comment="消息类型: task_handled/exception_raised/new_task/admin_command/system/task_dispatched/task_accepted/task_rejected/task_urged/task_stale/task_completed/task_verified")
    title = Column(String(200), nullable=False, comment="消息标题")
    content = Column(String(1000), comment="消息正文")
    level = Column(String(16), default="info", comment="级别: info/warning/error/success")
    target_role = Column(String(32), nullable=False, index=True, comment="目标角色: admin/operator/both")
    target_operator_id = Column(Integer, nullable=True, index=True, comment="目标操作员ID(仅operator时)")
    from_user_id = Column(Integer, nullable=True, index=True, comment="发送者用户ID")
    from_role = Column(String(16), nullable=True, comment="发送者角色: admin/operator")
    from_name = Column(String(50), nullable=True, comment="发送者名称")
    related_tracking = Column(String(64), nullable=True, comment="关联运单号")
    related_chute = Column(String(50), nullable=True, comment="关联分拣口")
    related_decision_id = Column(String(36), nullable=True, index=True, comment="关联分拣决策ID")
    is_read_admin = Column(Boolean, default=False, comment="管理员是否已读")
    is_read_operator = Column(Boolean, default=False, comment="操作员是否已读")
    read_at = Column(DateTime, nullable=True, comment="读取时间")
