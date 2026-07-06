"""系统配置模型"""
from sqlalchemy import Column, Integer, String, Text
from ..database import Base
from .base import TimestampMixin


class Config(Base, TimestampMixin):
    __tablename__ = "configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module = Column(String(50), nullable=False, comment="模块: general/ocr/sorting/notification")
    config_key = Column(String(100), nullable=False, comment="配置键")
    config_value = Column(Text, comment="配置值")
    value_type = Column(String(20), default="string", comment="值类型: string/int/float/bool/json")
    version = Column(Integer, default=1, comment="版本号")
    description = Column(String(200), comment="配置描述")


class ConfigHistory(Base, TimestampMixin):
    __tablename__ = "config_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(Integer, nullable=False, comment="配置ID")
    module = Column(String(50), comment="模块")
    config_key = Column(String(100), comment="配置键")
    old_value = Column(Text, comment="旧值")
    new_value = Column(Text, comment="新值")
    changed_by = Column(Integer, comment="修改人ID")
    version = Column(Integer, comment="版本号")
