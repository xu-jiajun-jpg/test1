"""FastAPI 应用入口"""
import os
os.environ["PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT"] = "0"
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from concurrent.futures import ThreadPoolExecutor

from .config import CORS_ORIGINS, UPLOADS_DIR
from .routers import auth, upload, ocr, barcode, sorting, dashboard
from .routers import exception_router, chute, operator_router, system_config, export, alert_router, user_mgmt, track
from .routers import scheduling, optimization, remote_ops_router, demo, logistics, message_router
from .routers import task_dispatch, task_accept, task_monitor, sla_config_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Startup] 上传目录: {UPLOADS_DIR}")

    # 从DB恢复活跃配送追踪到内存（防止重启丢失）
    try:
        from .services.delivery_tracking import recover_active_deliveries
        recover_active_deliveries()
    except Exception as e:
        print(f"[Startup] 配送追踪恢复跳过: {e}")

    # 启动后台告警检查任务
    alert_task = asyncio.create_task(_auto_alert_check())

    # 启动SLA监控协程
    sla_task = asyncio.create_task(_start_sla_monitor())

    # PaddleOCR在后台线程预热，不阻塞启动（可能耗时数分钟）
    def _warmup_ocr():
        try:
            from .services.ocr_service import get_ocr_engine
            get_ocr_engine()
            print("[Startup] PaddleOCR引擎预热完成")
        except Exception as e:
            print(f"[Startup] PaddleOCR预热跳过: {e}")

    executor = ThreadPoolExecutor(max_workers=1)
    ocr_future = executor.submit(_warmup_ocr)

    yield

    alert_task.cancel()
    sla_task.cancel()
    executor.shutdown(wait=False)
    print("[Shutdown] 应用关闭")


async def _auto_alert_check():
    """每60秒自动检查告警规则"""
    await asyncio.sleep(15)  # 启动后等待15秒
    while True:
        try:
            from .database import SessionLocal
            from .routers.alert_router import check_alerts_internal
            from .websocket.manager import manager as ws_manager
            db = SessionLocal()
            alerts = check_alerts_internal(db)
            if alerts:
                for a in alerts:
                    await ws_manager.broadcast("dashboard", {
                        "event": "alert_triggered",
                        "data": a
                    })
            db.close()
        except Exception:
            pass
        await asyncio.sleep(60)


async def _start_sla_monitor():
    """启动SLA监控后台协程"""
    try:
        from .services.sla_monitor import sla_monitor_loop
        await sla_monitor_loop()
    except Exception as e:
        print(f"[Startup] SLA监控启动失败: {e}")


app = FastAPI(
    title="物流分拣平台 API",
    description="基于图像特征识别的物流中心分拣平台",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(upload.router)
app.include_router(ocr.router)
app.include_router(barcode.router)
app.include_router(sorting.router)
app.include_router(exception_router.router)
app.include_router(chute.router)
app.include_router(operator_router.router)
app.include_router(system_config.router)
app.include_router(export.router)
app.include_router(alert_router.router)
app.include_router(user_mgmt.router)
app.include_router(track.router)
app.include_router(dashboard.router)
app.include_router(scheduling.router)
app.include_router(optimization.router)
app.include_router(remote_ops_router.router)
app.include_router(demo.router)
app.include_router(demo.device_router)
app.include_router(logistics.router)
app.include_router(message_router.router)
app.include_router(task_dispatch.router)
app.include_router(task_accept.router)
app.include_router(task_monitor.router)
app.include_router(sla_config_router.router)


# 静态文件
if UPLOADS_DIR.exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

from pathlib import Path
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


@app.get("/")
async def root():
    return {"message": "物流分拣平台 API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}
