"""应用配置管理"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"

# 数据库 — 请根据实际环境修改密码
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "123456")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "sorting_platform")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# JWT
SECRET_KEY = os.getenv("SECRET_KEY", "sort-platform-secret-key-2026")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# 上传
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Redis（开发阶段可选）
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 分页
PAGE_SIZE_DEFAULT = 20

# CORS
CORS_ORIGINS = ["http://localhost:8080", "http://localhost:5173", "http://127.0.0.1:8080", "http://localhost:8081"]

# ===== 物流配送全局配置 =====
# 唯一发货起点（硬编码，符合国内物流中心辐射模型）
ORIGIN_CITY = "南昌"
ORIGIN_PROVINCE = "江西"
ORIGIN_LNG = 115.8582
ORIGIN_LAT = 28.6829
