"""分拣人员模型"""
from sqlalchemy import Column, Integer, String, Boolean
from ..database import Base
from .base import TimestampMixin


class Operator(Base, TimestampMixin):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(32), unique=True, nullable=False, comment="工号")
    name = Column(String(50), nullable=False, comment="姓名")
    phone = Column(String(20), comment="联系电话")
    status = Column(String(16), default="active", comment="状态: active/inactive")
    shift = Column(String(32), comment="排班: morning/afternoon/night")


class OperatorChute(Base, TimestampMixin):
    __tablename__ = "operator_chutes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    operator_id = Column(Integer, nullable=False, index=True, comment="操作员ID")
    chute_code = Column(String(50), nullable=False, comment="分拣口编码")
