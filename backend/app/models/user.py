"""用户与角色模型"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum, Text, JSON
from sqlalchemy.orm import relationship
from ..database import Base
from .base import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    display_name = Column(String(50), comment="显示名称")
    role = Column(
        SAEnum("operator", "supervisor", "admin", "maintainer", name="user_role"),
        default="operator",
        comment="角色",
    )
    operator_id = Column(Integer, nullable=True, index=True, comment="关联的操作员ID（分拣人员）")
    is_active = Column(Boolean, default=True, comment="是否启用")
    last_login = Column(DateTime, comment="最后登录时间")


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False, comment="角色名称")
    code = Column(String(20), unique=True, nullable=False, comment="角色编码")
    permissions = Column(JSON, comment="权限JSON")
    description = Column(String(200), comment="角色描述")
