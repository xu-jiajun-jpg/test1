"""用户权限管理 — F14"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import bcrypt
from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..models.user import User, Role
from ..utils.response import paginated

router = APIRouter(prefix="/api/users", tags=["用户管理"])

@router.get("")
def list_users(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    total = db.query(User).count()
    items = db.query(User).offset((page - 1) * page_size).limit(page_size).all()
    return paginated([{"id": u.id, "username": u.username, "display_name": u.display_name, "role": u.role, "is_active": u.is_active} for u in items], total, page, page_size)

@router.post("")
def create_user(data: dict, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == data["username"]).first():
        raise HTTPException(400, "用户名已存在")
    hashed = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt())
    u = User(username=data["username"], password_hash=hashed.decode(), display_name=data.get("display_name", ""), role=data.get("role", "operator"))
    db.add(u); db.commit(); db.refresh(u)
    return {"code": 200, "message": "创建成功", "data": {"id": u.id}}

@router.put("/{user_id}")
def update_user(user_id: int, data: dict, db: Session = Depends(get_db)):
    u = db.query(User).get(user_id)
    if not u: raise HTTPException(404, "不存在")
    for k, v in data.items():
        if k == "password": v = bcrypt.hashpw(v.encode(), bcrypt.gensalt()).decode(); setattr(u, "password_hash", v)
        elif hasattr(u, k): setattr(u, k, v)
    db.commit()
    return {"code": 200}

@router.get("/roles")
def list_roles(db: Session = Depends(get_db)):
    roles = db.query(Role).all()
    return {"code": 200, "data": [{"id": r.id, "name": r.name, "code": r.code, "permissions": r.permissions} for r in roles]}
