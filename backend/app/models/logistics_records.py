"""车辆发车记录 & 包裹配送记录 — 持久化模型"""
import json
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, func
from ..database import Base
from .base import TimestampMixin


class VehicleRecord(Base, TimestampMixin):
    """车辆发车记录 — 每次发车创建一条"""
    __tablename__ = "vehicle_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String(50), nullable=False, index=True, comment="车辆ID")
    waypoints_json = Column(Text, comment="路点JSON: [{lng,lat,name}]")
    speed_kmh = Column(Float, default=40, comment="速度km/h")
    total_distance_km = Column(Float, default=0, comment="总距离")
    bound_packages = Column(Integer, default=0, comment="绑定包裹数")
    status = Column(String(20), default="running", comment="running/arrived/stopped")
    finished_at = Column(DateTime, nullable=True, comment="完成/停止时间")


class DeliveryRecord(Base, TimestampMixin):
    """包裹配送记录 — 每次绑定/状态变更记录"""
    __tablename__ = "delivery_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tracking_number = Column(String(64), nullable=False, index=True, comment="运单号")
    vehicle_id = Column(String(50), nullable=True, index=True, comment="承运车辆ID")
    origin = Column(String(50), default="南昌", comment="发货地")
    destination = Column(String(100), default="", comment="目的地")
    district = Column(String(32), default="", comment="配送分区")
    node_status = Column(Integer, default=0, comment="运输节点0-4")
    node_status_name = Column(String(50), default="已揽收", comment="节点名称")
    eta_minutes = Column(Float, default=0, comment="预计到达分钟")
    active = Column(Integer, default=1, comment="是否活跃 1=活跃 0=已结束")
