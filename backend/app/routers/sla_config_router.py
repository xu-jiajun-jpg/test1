"""SLA超时配置管理路由"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..models.sla_config import SlaConfig

router = APIRouter(prefix="/api/sla-config", tags=["SLA配置管理"])


class SlaConfigRequest(BaseModel):
    chute_code: str
    chute_name: str = ""
    accept_timeout: int = 10
    process_timeout: int = 30
    severity: str = "warning"
    escalation_action: str = "notify_admin"
    is_active: bool = True
    description: str = ""


@router.get("")
def list_sla_configs(db: Session = Depends(get_db)):
    configs = db.query(SlaConfig).order_by(SlaConfig.chute_code).all()
    return {
        "code": 200,
        "data": [
            {
                "id": c.id,
                "chute_code": c.chute_code,
                "chute_name": c.chute_name or "",
                "accept_timeout": c.accept_timeout,
                "process_timeout": c.process_timeout,
                "severity": c.severity,
                "escalation_action": c.escalation_action,
                "is_active": c.is_active,
                "description": c.description or "",
            }
            for c in configs
        ],
    }


@router.post("")
def create_sla_config(req: SlaConfigRequest, db: Session = Depends(get_db)):
    existing = db.query(SlaConfig).filter(SlaConfig.chute_code == req.chute_code).first()
    if existing:
        raise HTTPException(400, "该分拣口的SLA配置已存在")
    cfg = SlaConfig(**req.model_dump())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return {"code": 200, "message": "SLA配置创建成功", "data": {"id": cfg.id}}


@router.put("/{config_id}")
def update_sla_config(config_id: int, req: SlaConfigRequest, db: Session = Depends(get_db)):
    cfg = db.query(SlaConfig).get(config_id)
    if not cfg:
        raise HTTPException(404, "配置不存在")
    for k, v in req.model_dump().items():
        setattr(cfg, k, v)
    db.commit()
    return {"code": 200, "message": "更新成功"}


@router.delete("/{config_id}")
def delete_sla_config(config_id: int, db: Session = Depends(get_db)):
    cfg = db.query(SlaConfig).get(config_id)
    if not cfg:
        raise HTTPException(404, "配置不存在")
    db.delete(cfg)
    db.commit()
    return {"code": 200, "message": "已删除"}
