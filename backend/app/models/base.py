"""模型基类"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.mysql import CHAR
from ..database import Base


def gen_uuid():
    return uuid.uuid4().hex


def gen_id():
    return str(uuid.uuid4())


class TimestampMixin:
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
