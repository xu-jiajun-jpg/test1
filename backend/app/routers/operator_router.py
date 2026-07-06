"""分拣人员管理 — F09"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel
from ..database import get_db
from ..models.operator import Operator, OperatorChute
from ..models.sorting import SortingChute, SortingDecision
from ..models.ocr import OCRResult
from ..models.exception import ExceptionRecord
from ..middleware.auth_middleware import get_current_user_id
from ..utils.response import paginated
from ..websocket.manager import manager as ws_manager
from ..models.message import MessageRecord
from .message_router import create_message

router = APIRouter(prefix="/api/operators", tags=["人员管理"])

@router.get("")
def list_operators(page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    total = db.query(Operator).count()
    items = db.query(Operator).offset((page - 1) * page_size).limit(page_size).all()
    # 附带每个人员绑定的分拣口
    data = []
    for o in items:
        chutes = db.query(OperatorChute).filter(OperatorChute.operator_id == o.id).all()
        data.append({"id": o.id, "employee_id": o.employee_id, "name": o.name, "phone": o.phone,
                     "status": o.status, "shift": o.shift,
                     "chutes": [c.chute_code for c in chutes]})
    return paginated(data, total, page, page_size)

@router.post("")
def create_operator(data: dict, db: Session = Depends(get_db)):
    if db.query(Operator).filter(Operator.employee_id == data["employee_id"]).first():
        raise HTTPException(400, "工号已存在")
    o = Operator(**data); db.add(o); db.commit(); db.refresh(o)
    return {"code": 200, "message": "创建成功", "data": {"id": o.id}}

@router.put("/{op_id}")
def update_operator(op_id: int, data: dict, db: Session = Depends(get_db)):
    o = db.query(Operator).get(op_id)
    if not o: raise HTTPException(404, "不存在")
    for k, v in data.items(): setattr(o, k, v)
    db.commit()
    return {"code": 200, "message": "更新成功"}

# ===== 分拣口绑定 =====
@router.get("/{op_id}/chutes")
def get_operator_chutes(op_id: int, db: Session = Depends(get_db)):
    items = db.query(OperatorChute).filter(OperatorChute.operator_id == op_id).all()
    return {"code": 200, "data": [{"id": c.id, "chute_code": c.chute_code} for c in items]}

@router.post("/{op_id}/chutes")
def bind_chute(op_id: int, data: dict, db: Session = Depends(get_db)):
    """为分拣人员绑定分拣口（CH-006异常口仅允许一对一绑定）"""
    chute_code = data.get("chute_code")
    if not chute_code: raise HTTPException(400, "缺少chute_code")

    # CH-006 一对一约束：一个操作员只能绑 CH-006，CH-006 也只能被一个人绑定
    if chute_code == "CH-006":
        existing = db.query(OperatorChute).filter(
            OperatorChute.chute_code == "CH-006",
            OperatorChute.operator_id != op_id
        ).first()
        if existing:
            raise HTTPException(400, "CH-006异常暂存口已绑定其他分拣员，每口仅限一人负责")

    exists = db.query(OperatorChute).filter(
        OperatorChute.operator_id == op_id, OperatorChute.chute_code == chute_code
    ).first()
    if exists: return {"code": 200, "message": "已绑定"}
    db.add(OperatorChute(operator_id=op_id, chute_code=chute_code))
    db.commit()
    return {"code": 200, "message": "绑定成功"}

@router.delete("/{op_id}/chutes/{chute_code}")
def unbind_chute(op_id: int, chute_code: str, db: Session = Depends(get_db)):
    db.query(OperatorChute).filter(
        OperatorChute.operator_id == op_id, OperatorChute.chute_code == chute_code
    ).delete()
    db.commit()
    return {"code": 200, "message": "已解绑"}

# ===== 分拣员任务处理 =====
class HandleRequest(BaseModel):
    target_chute: str = ""   # 为空=仅确认，非空=分流到指定口
    handler: str = ""

@router.post("/tasks/{file_id}/handle")
async def handle_task(file_id: str, background_tasks: BackgroundTasks, req: HandleRequest = HandleRequest(), user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """操作员确认处理包裹（支持分流分拣），并推送到大屏"""
    from ..models.user import User
    from ..models.sorting import SortingDecision as SD
    import uuid as _uuid

    decision = db.query(SortingDecision).filter(SortingDecision.file_id == file_id).first()
    if not decision:
        raise HTTPException(404, "未找到该包裹的分拣记录")
    if decision.handled_at:
        return {"code": 200, "message": "该包裹已被处理过", "data": {"already_handled": True}}

    user = db.query(User).filter(User.id == user_id).first()
    operator = None
    if user:
        # 优先使用 operator_id 直连，降级兼容 display_name 匹配
        if user.operator_id:
            operator = db.query(Operator).filter(Operator.id == user.operator_id).first()
        else:
            operator = db.query(Operator).filter(
                (Operator.name == user.display_name) | (func.instr(user.display_name, Operator.name) > 0)
            ).first()

    handler_name = req.handler or (operator.name if operator else "操作员")

    # 如果指定了新的分拣口，创建新的分拣记录（分流）
    new_chute = req.target_chute.strip() if req.target_chute else ""
    if new_chute and new_chute != decision.target_chute and new_chute != "CH-006":
        # 标记旧记录
        decision.handled_at = datetime.utcnow()
        decision.handled_by = operator.id if operator else None
        # 创建新记录到指定分拣口
        sd = SD(
            decision_id=_uuid.uuid4().hex,
            file_id=file_id,
            tracking_number=decision.tracking_number,
            province=decision.province,
            city=decision.city,
            target_chute=new_chute,
            status="pending",
            priority=1,
            rule_id="R-OP",
            decision_time=datetime.utcnow(),
        )
        db.add(sd)
        db.commit()

        # → 推送大屏：已分流
        background_tasks.add_task(
            ws_manager.broadcast_task_handled,
            decision.tracking_number, new_chute, handler_name
        )

        # → 写入消息（管理员端可见）
        msg = create_message(
            category="task_handled",
            title=f"{handler_name} 分流包裹",
            content=f"包裹 {decision.tracking_number} 已从 {decision.target_chute or '自动'} 分流至 {new_chute}",
            level="info",
            target_role="admin",
            related_tracking=decision.tracking_number,
            related_chute=new_chute,
        )
        db.add(msg)
        db.commit()

        return {"code": 200, "message": f"已分流至 {new_chute}", "data": {
            "tracking_number": decision.tracking_number,
            "target_chute": new_chute,
            "handled_at": decision.handled_at.isoformat(),
        }}

    # 普通确认处理
    decision.handled_at = datetime.utcnow()
    decision.handled_by = operator.id if operator else None
    db.commit()

    # → 推送大屏：已处理
    background_tasks.add_task(
        ws_manager.broadcast_task_handled,
        decision.tracking_number, decision.target_chute or "未知", handler_name
    )

    # → 写入消息
    msg = create_message(
        category="task_handled",
        title=f"{handler_name} 确认处理",
        content=f"包裹 {decision.tracking_number} 已确认分拣至 {decision.target_chute or '未知'}",
        level="info",
        target_role="admin",
        related_tracking=decision.tracking_number,
        related_chute=decision.target_chute or "",
    )
    db.add(msg)
    db.commit()

    return {"code": 200, "message": "处理成功", "data": {
        "tracking_number": decision.tracking_number,
        "handled_at": decision.handled_at.isoformat(),
    }}


# ===== 分拣员任务查询 =====
@router.get("/my/tasks")
def my_tasks(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """根据当前登录用户查询绑定分拣口的包裹任务"""
    from ..models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user: return {"code": 404, "message": "用户不存在"}

    # 优先使用 operator_id 直连，再通过 display_name 匹配
    operator = None
    if user.operator_id:
        operator = db.query(Operator).filter(Operator.id == user.operator_id).first()
    else:
        operator = db.query(Operator).filter(
            (Operator.name == user.display_name) | (func.instr(user.display_name, Operator.name) > 0)
        ).first()
    if not operator: return {"code": 200, "data": {"chutes": [], "tasks": []}}

    chutes = db.query(OperatorChute).filter(OperatorChute.operator_id == operator.id).all()
    chute_codes = [c.chute_code for c in chutes]

    # 查询这些分拣口下的所有包裹（活跃+最近已完成）
    decisions = db.query(SortingDecision).filter(
        SortingDecision.target_chute.in_(chute_codes) if chute_codes else False,
        SortingDecision.status.in_([
            "pending", "dispatched", "accepted", "processing",
            "awaiting_dispatch",  # 操作员已申请发车等待审批
            "completed", "verified",
            "rejected", "stale", "failed",
        ]),
    ).order_by(
        # 活跃状态优先，已完成/已核验沉底
        case(
            (SortingDecision.status.in_(["pending", "dispatched"]), 0),
            (SortingDecision.status.in_(["accepted"]), 1),
            (SortingDecision.status.in_(["processing"]), 2),
            else_=9,
        ),
        SortingDecision.decision_time.desc()
    ).limit(200).all()

    # 批量获取OCR结果
    file_ids = [d.file_id for d in decisions]
    ocr_map = {}
    if file_ids:
        ocrs = db.query(OCRResult).filter(OCRResult.file_id.in_(file_ids)).order_by(OCRResult.created_at.desc()).all()
        for o in ocrs:
            if o.file_id not in ocr_map:
                ocr_map[o.file_id] = o

    tasks = []
    for d in decisions:
        ocr = ocr_map.get(d.file_id)
        # 查询处理人名称
        handler_name = ""
        if d.handled_by:
            handler = db.query(Operator).filter(Operator.id == d.handled_by).first()
            handler_name = handler.name if handler else ""
        tasks.append({
            "task_id": f"{d.file_id[:8]}",
            "file_id": d.file_id,
            "decision_id": getattr(d, "decision_id", None),
            "tracking_number": d.tracking_number,
            "province": d.province, "city": d.city, "district": d.district,
            "target_chute": d.target_chute, "status": d.status,
            "ocr_status": ocr.status if ocr else "",
            "receiver_name": ocr.receiver_name if ocr else "",
            "phone": ocr.phone if ocr else "",
            "decision_time": d.decision_time.isoformat() if d.decision_time else "",
            "handled_by_name": handler_name,
            "urge_count": d.urge_count or 0,
        })

    return {"code": 200, "data": {
        "operator_name": operator.name,
        "shift": operator.shift,
        "chutes": chute_codes,
        "tasks": tasks,
    }}


# ===== 异常上报 =====
class ExceptionReportRequest(BaseModel):
    file_id: str
    tracking_number: str = ""
    target_chute: str = ""
    exception_type: str = "damage"  # damage / barcode_unreadable / district_mismatch / oversized / other
    note: str = ""

EXCEPTION_TYPE_MAP = {
    "damage": "破损/渗漏",
    "barcode_unreadable": "条码无法识别",
    "district_mismatch": "分区不匹配",
    "oversized": "包裹超规",
    "other": "其他异常",
}

@router.post("/tasks/exception")
async def report_exception(req: ExceptionReportRequest, background_tasks: BackgroundTasks, user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """操作员上报异常包裹"""
    from ..models.user import User
    import uuid as _uuid

    user = db.query(User).filter(User.id == user_id).first()
    operator = None
    if user:
        # 优先使用 operator_id 直连，降级兼容 display_name 匹配
        if user.operator_id:
            operator = db.query(Operator).filter(Operator.id == user.operator_id).first()
        else:
            operator = db.query(Operator).filter(
                (Operator.name == user.display_name) | (func.instr(user.display_name, Operator.name) > 0)
            ).first()

    handler_name = operator.name if operator else "操作员"

    # 写入异常记录
    type_label = EXCEPTION_TYPE_MAP.get(req.exception_type, req.exception_type)
    exc = ExceptionRecord(
        exception_id=_uuid.uuid4().hex,
        file_id=req.file_id,
        tracking_number=req.tracking_number or "",
        exception_type=f"{req.exception_type}({type_label})",
        description=req.note or type_label,
        severity="medium",
        status="open",
        reported_by=handler_name,
        reported_at=datetime.utcnow(),
    )
    db.add(exc)

    # 标记分拣决策为异常
    if req.file_id:
        decision = db.query(SortingDecision).filter(SortingDecision.file_id == req.file_id).first()
        if decision:
            decision.handled_at = datetime.utcnow()
            if req.exception_type == "district_mismatch":
                decision.status = "failed"
            else:
                decision.status = "failed"

    db.commit()

    # → 推送大屏：异常告警
    exc_data = {
        "exception_id": exc.exception_id,
        "file_id": req.file_id,
        "tracking_number": req.tracking_number,
        "exception_type": type_label,
        "note": req.note,
        "reported_by": handler_name,
        "target_chute": req.target_chute,
    }
    background_tasks.add_task(ws_manager.broadcast_exception, exc_data)

    # → 写入消息（管理员端可见，critical级别）
    msg = create_message(
        category="exception_raised",
        title=f"⚠️ {handler_name} 上报异常",
        content=f"包裹 {req.tracking_number} 异常: {type_label}{' - ' + req.note if req.note else ''} ({req.target_chute or '未知分拣口'})",
        level="error",
        target_role="admin",
        related_tracking=req.tracking_number,
        related_chute=req.target_chute or "",
    )
    db.add(msg)
    db.commit()

    return {"code": 200, "message": f"异常已上报: {type_label}", "data": exc_data}


# ===== 获取操作员统计（供大屏使用） =====
@router.get("/stats")
def operator_stats(db: Session = Depends(get_db)):
    """获取所有操作员及分拣口统计"""
    operators = db.query(Operator).filter(Operator.status == "active").all()
    result = []
    for o in operators:
        chutes = db.query(OperatorChute).filter(OperatorChute.operator_id == o.id).all()
        chute_codes = [c.chute_code for c in chutes]

        # 统计该操作员对应分拣口的待处理包裹数
        pending = 0
        handled = 0
        if chute_codes:
            pending = db.query(SortingDecision).filter(
                SortingDecision.target_chute.in_(chute_codes),
                SortingDecision.handled_at == None,
            ).count()
            handled = db.query(SortingDecision).filter(
                SortingDecision.target_chute.in_(chute_codes),
                SortingDecision.handled_at != None,
            ).count()

        result.append({
            "operator_id": o.id,
            "name": o.name,
            "shift": o.shift,
            "status": o.status,
            "chutes": chute_codes,
            "pending": pending,
            "handled": handled,
        })
    return {"code": 200, "data": result}


# ===== 管理员指令 =====
class AdminCommand(BaseModel):
    operator_id: int
    message: str

@router.post("/command")
async def send_command(req: AdminCommand, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """管理员向操作员发送指令"""
    background_tasks.add_task(ws_manager.notify_operator_command, req.operator_id, req.message)

    # → 写入消息（操作员端可见）
    msg = create_message(
        category="admin_command",
        title="管理员指令",
        content=req.message,
        level="warning",
        target_role="operator",
        target_operator_id=req.operator_id,
    )
    db.add(msg)
    db.commit()

    return {"code": 200, "message": "指令已发送"}
