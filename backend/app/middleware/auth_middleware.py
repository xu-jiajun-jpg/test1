"""JWT认证中间件 — 支持操作员上下文解析"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from ..config import SECRET_KEY, JWT_ALGORITHM

security = HTTPBearer(auto_error=False)


def _decode_payload(credentials):
    """共用JWT解码"""
    if not credentials:
        raise HTTPException(status_code=401, detail="请先登录")
    try:
        return jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token无效或已过期")


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """从Token中解析当前用户ID"""
    payload = _decode_payload(credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token无效")
    return int(user_id)


def get_current_operator_context(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    从JWT中提取操作员上下文。

    返回:
        {
            "user_id": int,
            "role": str,
            "operator_id": int | None,
            "chute_codes": list[str],
        }
    """
    payload = _decode_payload(credentials)
    user_id = int(payload.get("sub", 0))
    role = payload.get("role", "operator")
    operator_id = payload.get("operator_id")
    chutes_str = payload.get("chutes", "")
    chute_codes = [c.strip() for c in chutes_str.split(",") if c.strip()] if chutes_str else []
    return {
        "user_id": user_id,
        "role": role,
        "operator_id": int(operator_id) if operator_id is not None else None,
        "chute_codes": chute_codes,
    }


def get_optional_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int | None:
    """可选认证（匿名也可访问）"""
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return int(payload.get("sub", 0))
    except JWTError:
        return None
