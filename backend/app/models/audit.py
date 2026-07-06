"""审计日志模型"""
from sqlalchemy import Column, Integer, String, Text
from ..database import Base
from .base import TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, comment="操作人ID")
    username = Column(String(50), comment="操作人用户名")
    action = Column(String(50), nullable=False, comment="操作类型")
    resource = Column(String(100), comment="操作资源")
    resource_id = Column(String(50), comment="资源ID")
    detail = Column(Text, comment="操作详情JSON")
    ip_address = Column(String(45), comment="IP地址")
