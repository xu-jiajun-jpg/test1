"""认证路由 — 登录/注册 + 操作员上下文注入"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import bcrypt
from jose import jwt

from ..database import get_db
from ..models.user import User
from ..models.operator import Operator, OperatorChute
from ..schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from ..config import SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from ..middleware.auth_middleware import get_current_user_id

router = APIRouter(prefix="/api/auth", tags=["认证"])


def _resolve_operator_chutes(user: User, db: Session) -> tuple[int | None, list[str]]:
    """获取 User 关联的 operator 信息和分拣口列表"""
    if user.role not in ("operator", "supervisor"):
        return None, []
    operator = None
    if user.operator_id:
        operator = db.query(Operator).filter(Operator.id == user.operator_id).first()
    else:
        # 降级兼容旧数据
        operator = db.query(Operator).filter(
            (Operator.name == user.display_name)
            | (func.instr(user.display_name, Operator.name) > 0)
        ).first()
    if not operator:
        return None, []
    chutes = db.query(OperatorChute).filter(
        OperatorChute.operator_id == operator.id
    ).all()
    return operator.id, sorted(set(c.chute_code for c in chutes))


def create_token(user_id: int, role: str = "operator",
                 operator_id: int | None = None,
                 chutes: list[str] | None = None,
                 is_ch006: bool = False) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "role": role,
    }
    if operator_id is not None:
        payload["operator_id"] = operator_id
    if chutes:
        payload["chutes"] = ",".join(chutes)
    if is_ch006:
        payload["is_ch006"] = True
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 更新最后登录时间
    user.last_login = datetime.utcnow()
    db.commit()

    # 解析操作员上下文
    operator_id, chute_codes = _resolve_operator_chutes(user, db)

    # CH-006异常口检测：标记该操作员是否负责异常处理
    is_ch006 = "CH-006" in chute_codes if chute_codes else False

    token = create_token(user.id, user.role, operator_id, chute_codes, is_ch006)
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "operator_id": operator_id,
            "chute_codes": chute_codes,
            "is_ch006": is_ch006,
        }
    )


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt())
    user = User(
        username=req.username,
        password_hash=hashed.decode(),
        display_name=req.display_name or req.username,
        role="operator",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    operator_id, chute_codes = _resolve_operator_chutes(user, db)
    token = create_token(user.id, user.role, operator_id, chute_codes)
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
            "operator_id": operator_id,
            "chute_codes": chute_codes,
        }
    )


@router.get("/me")
def get_me(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }
