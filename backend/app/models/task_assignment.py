"""任务派发关系模型 — 记录管理员→操作员的派单/拒收/改派链路"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from ..database import Base
from .base import gen_uuid, TimestampMixin


class TaskAssignment(Base, TimestampMixin):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignment_id = Column(String(36), unique=True, nullable=False, default=gen_uuid, index=True, comment="派发唯一标识")
    decision_id = Column(String(36), nullable=False, index=True, comment="关联分拣决策ID")
    file_id = Column(String(36), nullable=False, index=True, comment="关联上传文件ID")
    operator_id = Column(Integer, nullable=False, index=True, comment="操作员ID")
    operator_name = Column(String(32), comment="操作员名称(冗余)")
    chute_code = Column(String(50), comment="目标分拣口")
    # 派发状态：dispatched/accepted/rejected/completed
    status = Column(String(16), default="dispatched", comment="派发状态")
    reject_reason = Column(String(200), comment="拒收原因")
    assigned_at = Column(DateTime, comment="派发时间")
    accepted_at = Column(DateTime, nullable=True, comment="接收时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    note = Column(Text, comment="备注")
