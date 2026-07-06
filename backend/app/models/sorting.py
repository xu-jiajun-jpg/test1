"""分拣决策、规则、分拣口模型 — 9态任务生命周期"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from ..database import Base
from .base import gen_uuid, TimestampMixin


class SortingRule(Base, TimestampMixin):
    __tablename__ = "sorting_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(50), unique=True, nullable=False, index=True, comment="规则标识")
    province = Column(String(32), comment="目标省份")
    city = Column(String(32), comment="目标城市")
    district = Column(String(32), comment="目标区县")
    target_chute = Column(String(50), nullable=False, comment="目标分拣口编码")
    priority = Column(Integer, default=99, comment="优先级(1最高)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(String(200), comment="规则描述")


class SortingDecision(Base, TimestampMixin):
    __tablename__ = "sorting_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String(36), unique=True, nullable=False, default=gen_uuid, index=True, comment="决策标识")
    file_id = Column(String(36), nullable=False, index=True, comment="关联上传文件ID")
    tracking_number = Column(String(64), index=True, comment="运单号")
    province = Column(String(32), comment="目标省份")
    city = Column(String(32), comment="目标城市")
    district = Column(String(32), comment="目标区县")
    target_chute = Column(String(50), comment="目标分拣口")
    priority = Column(Integer, comment="决策优先级")
    rule_id = Column(String(50), comment="匹配规则ID")
    status = Column(
        String(16), default="pending",
        comment="决策状态(9态): pending/dispatched/accepted/processing/completed/verified/rejected/stale/failed",
    )
    decision_time = Column(DateTime, comment="决策时间")
    processing_time_ms = Column(Integer, comment="决策耗时(ms)")
    handled_at = Column(DateTime, nullable=True, comment="操作员处理时间")
    handled_by = Column(Integer, nullable=True, comment="处理人(operator_id)")
    # ===== 新增：SLA/超时/催办字段 =====
    sla_deadline = Column(DateTime, nullable=True, comment="SLA超时截止时间")
    escalated_at = Column(DateTime, nullable=True, comment="升级/滞留标记时间")
    urged_at = Column(DateTime, nullable=True, comment="最后催办时间")
    urge_count = Column(Integer, default=0, comment="催办次数")


class SortingChute(Base, TimestampMixin):
    __tablename__ = "sorting_chutes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chute_code = Column(String(50), unique=True, nullable=False, comment="分拣口编码")
    name = Column(String(100), comment="分拣口名称")
    location = Column(String(200), comment="物理位置")
    capacity = Column(Integer, default=1000, comment="容量(件/小时)")
    is_active = Column(Boolean, default=True, comment="是否启用")
    description = Column(String(200), comment="备注")
