"""异常记录模型 — 含SLA时效追踪"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SAEnum
from ..database import Base
from .base import gen_uuid, TimestampMixin


class ExceptionRecord(Base, TimestampMixin):
    __tablename__ = "exception_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exception_id = Column(String(36), unique=True, nullable=False, default=gen_uuid, index=True, comment="异常唯一标识")
    file_id = Column(String(36), nullable=False, index=True, comment="关联上传文件ID")
    tracking_number = Column(String(64), index=True, comment="运单号")
    exception_type = Column(String(64), comment="异常类型: damage/barcode_unreadable/district_mismatch/oversized/other/rejection")
    description = Column(String(500), comment="异常描述")
    severity = Column(String(16), default="medium", comment="严重程度: low/medium/high/critical")
    status = Column(String(16), default="open", comment="处理状态: open/processing/resolved/closed")
    reported_by = Column(String(50), comment="上报人")
    reported_at = Column(DateTime, comment="上报时间")
    detail = Column(Text, comment="异常详情JSON")
    resolved_by = Column(String(50), comment="处理人")
    resolution = Column(Text, comment="处理结果")
    # ===== 新增：SLA字段 =====
    sla_deadline = Column(DateTime, nullable=True, comment="SLA超时截止时间")
    escalated = Column(Boolean, default=False, comment="是否已升级告警")
    exceeded_at = Column(DateTime, nullable=True, comment="超时时间")
    related_decision_id = Column(String(36), nullable=True, index=True, comment="关联分拣决策ID")
