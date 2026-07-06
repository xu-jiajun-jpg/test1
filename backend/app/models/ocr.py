"""OCR识别结果模型"""
from sqlalchemy import Column, Integer, String, Text, Enum as SAEnum, DateTime
from ..database import Base
from .base import TimestampMixin


class OCRResult(Base, TimestampMixin):
    __tablename__ = "ocr_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), nullable=False, index=True, comment="关联上传文件ID")
    raw_text = Column(Text, comment="OCR原始文本")
    receiver_name = Column(String(64), comment="收件人姓名")
    phone = Column(String(20), comment="收件人电话")
    province = Column(String(32), comment="省份")
    city = Column(String(32), comment="城市")
    district = Column(String(32), comment="区县")
    detail_address = Column(String(255), comment="详细地址")
    tracking_number = Column(String(64), index=True, comment="运单号")
    processing_time_ms = Column(Integer, comment="处理耗时(ms)")
    status = Column(
        SAEnum("auto_pass", "need_review", "manual_required", "not_waybill", name="ocr_status"),
        default="need_review",
        comment="识别状态",
    )
