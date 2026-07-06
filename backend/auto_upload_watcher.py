"""
工业相机自动上传监听器
监听指定文件夹（如通过USB连接的手机DCIM目录），
新图片出现时自动上传并触发OCR识别。
"""
import os
import sys
import time
import requests
from pathlib import Path

# ===== 配置 =====
API_BASE = "http://127.0.0.1:8001"
USERNAME = "admin"
PASSWORD = "admin123"

# 监听的文件夹（默认为命令行参数，否则手动设置）
# 手机通过USB连接后，一般在 此电脑\手机名\内部存储\DCIM\Camera
WATCH_DIR = sys.argv[1] if len(sys.argv) > 1 else None

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
CHECK_INTERVAL = 2  # 扫描间隔（秒）
# ==================


def login() -> str:
    """登录获取token"""
    resp = requests.post(f"{API_BASE}/api/auth/login", json={
        "username": USERNAME, "password": PASSWORD
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"]


def upload_file(file_path: Path, token: str) -> str | None:
    """上传单个文件，返回 file_id"""
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/api/upload/single",
            files={"file": (file_path.name, f, f"image/{file_path.suffix.lstrip('.')}")},
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
    resp.raise_for_status()
    data = resp.json()
    file_id = data["data"]["file_id"]
    print(f"  ✅ 上传成功: {file_path.name} → {file_id[:12]}...")
    return file_id


def run_ocr(file_id: str, token: str):
    """触发OCR识别"""
    resp = requests.post(
        f"{API_BASE}/api/ocr/recognize/{file_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    )
    data = resp.json()
    ocr_data = data.get("data", {}).get("ocr", {})
    fields = ocr_data.get("fields", {})
    tracking = fields.get("tracking_number", "?")
    province = fields.get("province", "?")
    confidence = ocr_data.get("confidence", 0)
    print(f"  🔍 OCR完成: 运单号={tracking} 省份={province} 置信度={confidence:.1f}%")


def scan_and_upload(known_files: set, token: str) -> set:
    """扫描目录，上传新文件"""
    if not WATCH_DIR or not os.path.isdir(WATCH_DIR):
        return known_files

    current_files = set()
    for f in Path(WATCH_DIR).iterdir():
        if f.is_file() and f.suffix.lower() in ALLOWED_EXTS:
            current_files.add(f.name)

    new_files = current_files - known_files
    for name in sorted(new_files):
        file_path = Path(WATCH_DIR) / name
        # 等待文件写入完成（避免上传不完整的文件）
        size1 = file_path.stat().st_size
        time.sleep(0.5)
        size2 = file_path.stat().st_size
        if size1 != size2 or size1 == 0:
            print(f"  ⏳ {name} 仍在写入中，稍后重试")
            continue

        try:
            print(f"\n📸 检测到新图片: {name}")
            file_id = upload_file(file_path, token)
            if file_id:
                run_ocr(file_id, token)
        except requests.HTTPError as e:
            print(f"  ❌ 请求失败: {e}")
        except Exception as e:
            print(f"  ❌ 处理出错: {e}")

    return current_files


def main():
    global WATCH_DIR

    print("=" * 55)
    print("  📸 工业相机自动上传监听器")
    print("  拍照 → 自动上传 → OCR识别 → 分拣决策")
    print("=" * 55)

    # 登录
    print("\n🔑 正在登录...")
    try:
        token = login()
        print(f"  ✅ 登录成功 ({USERNAME})")
    except Exception as e:
        print(f"  ❌ 登录失败: {e}")
        print("    请确保后端已启动: python run.py")
        return

    # 设置监听目录
    while not WATCH_DIR or not os.path.isdir(WATCH_DIR):
        if WATCH_DIR:
            print(f"\n  ❌ 路径不存在: {WATCH_DIR}")
        WATCH_DIR = input("\n📁 请输入要监听的文件夹路径（手机DCIM目录）: ").strip()
        if not WATCH_DIR:
            print("  已取消")
            return
        WATCH_DIR = os.path.abspath(WATCH_DIR)

    print(f"\n👀 开始监听: {WATCH_DIR}")
    print(f"   支持格式: {', '.join(ALLOWED_EXTS)}")
    print(f"   扫描间隔: {CHECK_INTERVAL}秒")
    print(f"   按 Ctrl+C 停止\n")

    known_files = set()
    try:
        while True:
            try:
                known_files = scan_and_upload(known_files, token)
            except requests.HTTPError as e:
                if e.response and e.response.status_code == 401:
                    print("🔑 Token过期，重新登录...")
                    token = login()
                    continue
                print(f"⚠ 网络错误: {e}")
            except Exception as e:
                print(f"⚠ 扫描异常: {e}")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n\n🛑 监听已停止")


if __name__ == "__main__":
    main()
