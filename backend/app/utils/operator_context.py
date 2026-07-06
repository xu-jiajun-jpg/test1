"""操作员上下文解析器 — 集中获取当前User关联的Operator及分拣口信息"""
from sqlalchemy.orm import Session
from ..models.user import User
from ..models.operator import Operator, OperatorChute


def resolve_operator_context(user_id: int, db: Session) -> dict | None:
    """
    从 User 出发，解析操作员上下文。

    返回:
        {
            "operator_id": int,
            "operator_name": str,
            "chute_codes": list[str],   # 当前用户绑定的所有分拣口
        }
    若用户不是操作员/主管或未关联 Operator，返回 None。
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    if user.role not in ("operator", "supervisor"):
        return None

    # 优先走 operator_id 直连
    operator = None
    if user.operator_id:
        operator = db.query(Operator).filter(Operator.id == user.operator_id).first()
    else:
        # 降级兼容：通过 display_name 模糊匹配（旧数据过渡期使用）
        from sqlalchemy import func
        operator = db.query(Operator).filter(
            (Operator.name == user.display_name)
            | (func.instr(user.display_name, Operator.name) > 0)
        ).first()

    if not operator:
        return None

    chutes = db.query(OperatorChute).filter(
        OperatorChute.operator_id == operator.id
    ).all()
    chute_codes = sorted(set(c.chute_code for c in chutes))

    return {
        "operator_id": operator.id,
        "operator_name": operator.name,
        "chute_codes": chute_codes,
    }
