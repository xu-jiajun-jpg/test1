"""文件处理工具"""
import os
import uuid
from datetime import datetime
from pathlib import Path
from ..config import MAX_UPLOAD_SIZE, ALLOWED_EXTENSIONS

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
    """校验文件扩展名和大小"""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"不支持的文件格式: {ext}，允许: {', '.join(ALLOWED_EXTENSIONS)}"
    if file_size > MAX_UPLOAD_SIZE:
        return False, f"文件大小超过限制: {file_size} > {MAX_UPLOAD_SIZE}"
    if file_size == 0:
        return False, "文件为空"
    return True, "ok"


def generate_file_path(original_name: str) -> tuple[str, str]:
    """生成存储路径 返回(相对路径, 绝对目录)"""
    now = datetime.now()
    date_dir = now.strftime("%Y-%m")
    ext = os.path.splitext(original_name)[1].lower()
    new_name = f"{uuid.uuid4().hex}{ext}"
    return f"{date_dir}/{new_name}", date_dir


def create_thumbnail(src_path: str, thumb_path: str, size=(300, 300)) -> bool:
    """生成缩略图"""
    if not HAS_PIL:
        return False
    try:
        img = Image.open(src_path)
        img.thumbnail(size, Image.LANCZOS)
        os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
        img.save(thumb_path)
        return True
    except Exception:
        return False
