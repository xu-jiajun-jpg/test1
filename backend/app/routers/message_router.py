"""消息中心 API — 角色隔离双向消息 + 精准投递 + 报错闭环"""
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from ..database import get_db
from ..models.message import MessageRecord
from ..models.user import User
from ..models.operator import Operator, OperatorChute
from ..middleware.auth_middleware import get_current_user_id
from ..utils.response import paginated

router = APIRouter(prefix="/api/messages", tags=["消息中心"])


# ===== 系统内部消息创建（供其他模块调用） =====
def create_message(
    category: str, title: str, content: str = "", level: str = "info",
    target_role: str = "both", target_operator_id: int = None,
    related_tracking: str = None, related_chute: str = None,
    related_decision_id: str = None,
    from_name: str = "系统", from_role: str = "system",
):
    return MessageRecord(
        message_id=uuid.uuid4().hex, category=category,
        title=title, content=content, level=level,
        target_role=target_role, target_operator_id=target_operator_id,
        related_tracking=related_tracking, related_chute=related_chute,
        related_decision_id=related_decision_id,
        from_name=from_name, from_role=from_role,
    )


# ===== 发送消息 =====
class SendMessageRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(default="", max_length=1000)
    level: str = Field(default="info")
    target_type: str = Field(default="all", description="all/operator/chute —管理员专用")
    target_operator_id: Optional[int] = Field(default=None)
    target_chute: Optional[str] = Field(default=None, max_length=50)
    related_tracking: Optional[str] = Field(default=None, max_length=64)


# ===== 辅助 =====
def _make_msg(**kw):
    kw.setdefault("is_read_admin", False)
    kw.setdefault("is_read_operator", False)
    return MessageRecord(
        message_id=uuid.uuid4().hex,
        **kw,
    )


# ===== 1. 发送消息（角色强隔离） =====
@router.post("/send")
def send_message(
    req: SendMessageRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    sender_role = user.role
    sender_name = user.display_name or user.username

    # ===== 操作员/主管：只允许向管理员报错 =====
    if sender_role in ("operator", "supervisor"):
        target_role = "admin"
        category = "error_report"
        if req.level == "info":
            req.level = "warning"
        msg = _make_msg(
            category=category,
            title=f"【报错】{req.title}",
            content=req.content,
            level=req.level,
            target_role=target_role,
            from_user_id=user_id, from_role=sender_role, from_name=sender_name,
            related_tracking=req.related_tracking,
            related_chute=req.target_chute,
            is_read_operator=True,  # 发送者自动已读
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        _ws_push(target_role, None, msg, sender_name, sender_role)
        return {"code": 200, "message": "报错已提交，管理员将尽快处理", "data": {
            "message_id": msg.message_id, "sender": sender_name,
            "created_at": msg.created_at.isoformat() if msg.created_at else "",
        }}

    # ===== 管理员：精准投递 =====
    category = "admin_directive"
    target_role = "operator"

    # 解析目标
    target_operator_id = None
    target_chute = None
    target_desc = ""

    if req.target_type == "all":
        target_desc = "全体操作员"
    elif req.target_type == "chute" and req.target_chute:
        target_chute = req.target_chute
        target_desc = f"分拣口 {req.target_chute}"
    elif req.target_type == "operator" and req.target_operator_id:
        target_operator_id = req.target_operator_id
        op = db.query(Operator).filter(Operator.id == target_operator_id).first()
        target_desc = f"操作员 {op.name}" if op else f"操作员#{target_operator_id}"

    msg = _make_msg(
        category=category,
        title=req.title,
        content=req.content,
        level=req.level,
        target_role=target_role,
        target_operator_id=target_operator_id,
        related_chute=target_chute or req.target_chute,
        related_tracking=req.related_tracking,
        from_user_id=user_id, from_role=sender_role, from_name=sender_name,
        is_read_admin=True,  # 发送者自动已读
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    _ws_push("operator", target_operator_id, msg, sender_name, sender_role)

    return {"code": 200, "message": f"已发送给 {target_desc}", "data": {
        "message_id": msg.message_id, "sender": sender_name,
        "created_at": msg.created_at.isoformat() if msg.created_at else "",
    }}


def _ws_push(target_role, target_operator_id, msg, sender_name, sender_role):
    try:
        from ..websocket.manager import manager as ws_manager
        import asyncio
        asyncio.ensure_future(ws_manager.broadcast_new_message(
            target_role, target_operator_id, {
                "message_id": msg.message_id, "title": msg.title,
                "content": msg.content, "level": msg.level,
                "category": msg.category, "sender_name": sender_name,
                "sender_role": sender_role,
                "created_at": msg.created_at.isoformat() if msg.created_at else "",
            }
        ))
    except Exception:
        pass


# ===== 2. 可选发送目标（管理员用） =====
@router.get("/targets")
def get_targets(db: Session = Depends(get_db)):
    """返回可选的操作员列表和分拣口列表"""
    operators = db.query(Operator).filter(Operator.status == "active").all()
    op_list = [{"operator_id": op.id, "name": op.name, "shift": op.shift or ""} for op in operators]

    chutes = db.query(OperatorChute.chute_code).distinct().order_by(OperatorChute.chute_code).all()
    chute_list = [c[0] for c in chutes if c[0]]

    return {"code": 200, "data": {"operators": op_list, "chutes": chute_list}}


# ===== 3. 消息列表（角色隔离 + 分拣口隔离 + 定向隔离 + 收发分离） =====
@router.get("")
def list_messages(
    role: str = Query("admin"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
    unread_only: bool = Query(False),
    sent_only: bool = Query(False, description="仅查询发件箱（当前用户发送的消息）"),
    category: str = Query(None),
    operator_id: int = Query(None, description="当前操作员ID（用于隔离过滤）"),
    chute_codes: str = Query(None, description="当前操作员所属分拣口，逗号分隔"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_, and_
    # 兼容 supervisor 角色当作 operator 处理
    effective_role = "operator" if role in ("supervisor",) else role

    query = db.query(MessageRecord)

    if sent_only:
        # 发件箱：仅显示当前用户发出的消息（跳过收件箱可见性过滤）
        query = query.filter(MessageRecord.from_user_id == user_id)
    elif effective_role == "admin":
        # 管理员：看到所有收件人为 admin/both 的消息 + 自己发送的消息
        query = query.filter(
            or_(
                MessageRecord.target_role.in_(["admin", "both"]),
                MessageRecord.from_user_id == user_id,
            )
        )
    else:
        # 操作员：三重可见性过滤 + 显式排除发给管理员的非本人消息
        user_owns = MessageRecord.from_user_id == user_id
        public_broadcast = and_(
            MessageRecord.target_role.in_(["operator", "both"]),
            MessageRecord.target_operator_id.is_(None),
            MessageRecord.related_chute.is_(None),
        )
        chute_list = [c.strip() for c in chute_codes.split(",") if c.strip()] if chute_codes else []
        chute_specific = and_(
            MessageRecord.target_role.in_(["operator", "both"]),
            MessageRecord.related_chute.in_(chute_list),
        ) if chute_list else None
        operator_specific = and_(
            MessageRecord.target_role.in_(["operator", "both"]),
            MessageRecord.target_operator_id == operator_id,
        ) if operator_id else None

        filters = [user_owns, public_broadcast]
        if chute_specific is not None:
            filters.append(chute_specific)
        if operator_specific is not None:
            filters.append(operator_specific)
        # 显式排除：target_role=admin 且不是本人发的（含 from_user_id=NULL 的旧数据）
        query = query.filter(or_(*filters)).filter(
            ~and_(
                MessageRecord.target_role == "admin",
                or_(
                    MessageRecord.from_user_id.is_(None),
                    MessageRecord.from_user_id != user_id,
                ),
            )
        )

    if category:
        query = query.filter(MessageRecord.category == category)
    if effective_role == "admin":
        if unread_only:
            query = query.filter(MessageRecord.is_read_admin == False)
    else:
        if unread_only:
            query = query.filter(MessageRecord.is_read_operator == False)

    total = query.count()
    items = query.order_by(MessageRecord.created_at.desc()).offset(
        (page - 1) * page_size).limit(page_size).all()

    data = [{
        "message_id": m.message_id, "category": m.category,
        "title": m.title, "content": m.content, "level": m.level,
        "target_role": m.target_role, "target_operator_id": m.target_operator_id,
        "from_name": m.from_name or "", "from_role": m.from_role or "",
        "related_tracking": m.related_tracking, "related_chute": m.related_chute,
        "is_read": m.is_read_admin if role == "admin" else m.is_read_operator,
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "read_at": m.read_at.isoformat() if m.read_at else None,
    } for m in items]

    return {**paginated(data, total, page, page_size), "unread_count": query.filter(
        MessageRecord.is_read_admin == False if role == "admin"
        else MessageRecord.is_read_operator == False
    ).count()}


# ===== 4. 未读计数（分拣口隔离） =====
@router.get("/unread-count")
def unread_count(
    role: str = Query("admin"),
    operator_id: int = Query(None, description="当前操作员ID"),
    chute_codes: str = Query(None, description="所属分拣口，逗号分隔"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_, and_
    query = db.query(MessageRecord)
    effective_role = "operator" if role in ("supervisor",) else role
    if effective_role == "admin":
        query = query.filter(
            or_(
                MessageRecord.target_role.in_(["admin", "both"]),
                MessageRecord.from_user_id == user_id,
            )
        )
        query = query.filter(MessageRecord.is_read_admin == False)
    else:
        # 操作员：三重可见性过滤
        user_owns = MessageRecord.from_user_id == user_id
        public_broadcast = and_(
            MessageRecord.target_role.in_(["operator", "both"]),
            MessageRecord.target_operator_id.is_(None),
            MessageRecord.related_chute.is_(None),
        )
        chute_list = [c.strip() for c in chute_codes.split(",") if c.strip()] if chute_codes else []
        chute_specific = and_(
            MessageRecord.target_role.in_(["operator", "both"]),
            MessageRecord.related_chute.in_(chute_list),
        ) if chute_list else None
        operator_specific = and_(
            MessageRecord.target_role.in_(["operator", "both"]),
            MessageRecord.target_operator_id == operator_id,
        ) if operator_id else None

        filters = [user_owns, public_broadcast]
        if chute_specific is not None:
            filters.append(chute_specific)
        if operator_specific is not None:
            filters.append(operator_specific)

        query = query.filter(or_(*filters)).filter(
            ~and_(
                MessageRecord.target_role == "admin",
                or_(
                    MessageRecord.from_user_id.is_(None),
                    MessageRecord.from_user_id != user_id,
                ),
            )
        )
        query = query.filter(MessageRecord.is_read_operator == False)

    return {"code": 200, "data": {"unread_count": query.count()}}


# ===== 5. 标记已读 =====
class MarkReadRequest(BaseModel):
    message_ids: list[str] = []
    mark_all: bool = False


@router.put("/read")
def mark_read(
    req: MarkReadRequest,
    role: str = Query("admin"),
    operator_id: int = Query(None, description="当前操作员ID"),
    chute_codes: str = Query(None, description="所属分拣口，逗号分隔"),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from sqlalchemy import or_, and_
    query = db.query(MessageRecord)
    effective_role = "operator" if role in ("supervisor",) else role

    if req.mark_all:
        # 使用与 list_messages 完全一致的可见性过滤
        if effective_role == "admin":
            query = query.filter(
                or_(
                    MessageRecord.target_role.in_(["admin", "both"]),
                    MessageRecord.from_user_id == user_id,
                )
            )
            query = query.filter(MessageRecord.is_read_admin == False)
        else:
            # 操作员：三重可见性过滤（与 list_messages 一致）
            user_owns = MessageRecord.from_user_id == user_id
            public_broadcast = and_(
                MessageRecord.target_role.in_(["operator", "both"]),
                MessageRecord.target_operator_id.is_(None),
                MessageRecord.related_chute.is_(None),
            )
            chute_list = [c.strip() for c in chute_codes.split(",") if c.strip()] if chute_codes else []
            chute_specific = and_(
                MessageRecord.target_role.in_(["operator", "both"]),
                MessageRecord.related_chute.in_(chute_list),
            ) if chute_list else None
            operator_specific = and_(
                MessageRecord.target_role.in_(["operator", "both"]),
                MessageRecord.target_operator_id == operator_id,
            ) if operator_id else None

            filters = [user_owns, public_broadcast]
            if chute_specific is not None:
                filters.append(chute_specific)
            if operator_specific is not None:
                filters.append(operator_specific)

            query = query.filter(or_(*filters))
            query = query.filter(MessageRecord.is_read_operator == False)
    elif req.message_ids:
        # 标记指定消息：只允许标记自己可见的消息
        query = query.filter(MessageRecord.message_id.in_(req.message_ids))
        # 额外安全检查：不能标记不属于自己的消息
        if effective_role == "admin":
            query = query.filter(
                or_(
                    MessageRecord.target_role.in_(["admin", "both"]),
                    MessageRecord.from_user_id == user_id,
                )
            )
    else:
        return {"code": 400, "message": "请指定 message_ids 或 mark_all"}

    count = 0
    for m in query.all():
        if effective_role == "admin":
            m.is_read_admin = True
        else:
            m.is_read_operator = True
        m.read_at = datetime.utcnow()
        count += 1
    db.commit()
    return {"code": 200, "message": f"已标记 {count} 条已读"}


# ===== 6. 清除 =====
@router.delete("/clean")
def clean_old(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    from sqlalchemy import func
    cutoff = func.datetime("now", f"-{days} days")
    deleted = db.query(MessageRecord).filter(
        MessageRecord.created_at < cutoff,
        MessageRecord.is_read_admin == True,
        MessageRecord.is_read_operator == True,
    ).delete()
    db.commit()
    return {"code": 200, "message": f"已清理 {deleted} 条历史消息"}
