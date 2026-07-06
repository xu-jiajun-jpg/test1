"""系统配置 — F10"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..models.config_model import Config, ConfigHistory

router = APIRouter(prefix="/api/config", tags=["系统配置"])


@router.get("")
def list_config(module: str = "", db: Session = Depends(get_db)):
    q = db.query(Config)
    if module: q = q.filter(Config.module == module)
    items = q.all()
    return {"code": 200, "data": [{"id": c.id, "module": c.module, "config_key": c.config_key, "config_value": c.config_value, "value_type": c.value_type, "description": c.description} for c in items]}


@router.post("")
def create_config(data: dict, db: Session = Depends(get_db)):
    cfg = Config(**data)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return {"code": 200, "message": "创建成功", "data": {"id": cfg.id}}


@router.put("/{cfg_id}")
def update_config(cfg_id: int, data: dict, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    cfg = db.query(Config).get(cfg_id)
    if not cfg: return {"code": 404}
    old_val = cfg.config_value
    cfg.config_value = str(data.get("config_value", data.get("value", old_val)))
    cfg.version += 1
    db.add(ConfigHistory(config_id=cfg.id, module=cfg.module, config_key=cfg.config_key, old_value=old_val, new_value=cfg.config_value, changed_by=user_id, version=cfg.version))
    db.commit()
    return {"code": 200, "message": "配置已更新"}


@router.delete("/{cfg_id}")
def delete_config(cfg_id: int, db: Session = Depends(get_db)):
    cfg = db.query(Config).get(cfg_id)
    if not cfg: return {"code": 404}
    db.delete(cfg)
    db.commit()
    return {"code": 200, "message": "已删除"}
