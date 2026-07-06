"""模块11+12：远程运维 + 多中心协同路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.remote_ops import RemoteOpsManager, MultiCenterManager

router = APIRouter(prefix="/api/ops", tags=["远程运维·多中心协同"])


@router.get("/devices")
def get_devices(db: Session = Depends(get_db)):
    return {"code": 200, "data": RemoteOpsManager.get_device_status(db)}


@router.post("/devices/{device_id}/adjust")
def adjust_device(device_id: int, data: dict):
    result = RemoteOpsManager.adjust_parameter(device_id, data.get("param", ""), data.get("value"))
    return {"code": 200, "data": result}


@router.get("/upgrade")
def get_upgrade():
    return {"code": 200, "data": RemoteOpsManager.get_upgrade_status()}


@router.get("/centers")
def get_centers(db: Session = Depends(get_db)):
    return {"code": 200, "data": MultiCenterManager.get_centers(db)}


@router.post("/centers/schedule")
def schedule_task(data: dict, db: Session = Depends(get_db)):
    result = MultiCenterManager.schedule_task(data, db)
    return {"code": 200, "data": result}


@router.post("/centers/failover/{center_id}")
def failover(center_id: int, db: Session = Depends(get_db)):
    result = MultiCenterManager.handle_failover(center_id, db)
    return {"code": 200, "data": result}
