"""统计数据与导出记录模型"""
from sqlalchemy import Column, Integer, Date, String, BigInteger
from ..database import Base
from .base import TimestampMixin


class DailyStats(Base, TimestampMixin):
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(Date, nullable=False, unique=True, comment="统计日期")
    total_uploaded = Column(Integer, default=0, comment="上传总数")
    ocr_processed = Column(Integer, default=0, comment="OCR处理数")
    ocr_success = Column(Integer, default=0, comment="OCR成功数")
    barcode_decoded = Column(Integer, default=0, comment="条码解码数")
    sorted = Column(Integer, default=0, comment="分拣决策数")
    success_count = Column(Integer, default=0, comment="成功数")
    fail_count = Column(Integer, default=0, comment="失败数")
    avg_processing_ms = Column(Integer, default=0, comment="平均处理耗时(ms)")
    total_file_size = Column(BigInteger, default=0, comment="总文件大小")


class ExportRecord(Base, TimestampMixin):
    __tablename__ = "export_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, comment="导出用户ID")
    export_type = Column(String(20), comment="导出类型: excel/csv/pdf")
    query_params = Column(String(500), comment="查询参数JSON")
    file_path = Column(String(500), comment="导出文件路径")
    row_count = Column(Integer, default=0, comment="导出行数")
    status = Column(String(16), default="success", comment="状态")
