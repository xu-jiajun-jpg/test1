"""上传记录模型"""
from sqlalchemy import Column, Integer, String, BigInteger, Float, Enum as SAEnum, DateTime
from sqlalchemy.orm import relationship
from ..database import Base
from .base import gen_uuid, TimestampMixin


class UploadRecord(Base, TimestampMixin):
    __tablename__ = "upload_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(36), unique=True, nullable=False, default=gen_uuid, index=True, comment="文件唯一标识")
    original_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="存储路径")
    thumbnail_path = Column(String(500), comment="缩略图路径")
    file_size = Column(BigInteger, nullable=False, comment="文件大小(字节)")
    package_length = Column(Float, comment="包裹长(cm)")
    package_width = Column(Float, comment="包裹宽(cm)")
    package_height = Column(Float, comment="包裹高(cm)")
    mime_type = Column(String(50), comment="MIME类型")
    uploader_id = Column(Integer, comment="上传者ID")
    status = Column(
        SAEnum("pending", "processing", "done", "failed", name="upload_status"),
        default="pending",
        comment="状态",
    )
