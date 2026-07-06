"""条码/二维码识别结果模型"""
from sqlalchemy import Column, Integer, String, Enum as SAEnum
from ..database import Base
from .base import TimestampMixin


class BarcodeResult(Base, TimestampMixin):
    __tablename__ = "barcode_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), nullable=False, index=True, comment="关联上传文件ID")
    barcode_type = Column(String(32), comment="条码类型: CODE128/EAN13/QR/DATA_MATRIX")
    barcode_data = Column(String(255), comment="解码数据")
    rect_x = Column(Integer, comment="条码位置X")
    rect_y = Column(Integer, comment="条码位置Y")
    rect_w = Column(Integer, comment="条码宽度")
    rect_h = Column(Integer, comment="条码高度")
    total_count = Column(Integer, default=0, comment="检测到的条码总数")
    fusion_result = Column(
        SAEnum("barcode", "ocr_fallback", "manual_required", name="fusion_status"),
        comment="融合结果",
    )
