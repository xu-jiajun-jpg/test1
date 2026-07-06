"""任务派发路由 — 管理员主动派单/催办/改派 + 分拣引擎自动派发"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import uuid as _uuid

from ..database import get_db
from ..middleware.auth_middleware import get_current_user_id
from ..models.sorting import SortingDecision
from ..models.operator import Operator, OperatorChute
from ..models.task_assignment import TaskAssignment
from ..models.message import MessageRecord
from ..models.exception import ExceptionRecord
from ..websocket.manager import manager as ws_manager
from ..services.sort_engine import SortRuleEngine

router = APIRouter(prefix="/api/tasks", tags=["任务派发·协同管理"])

# ===== 状态流转校验表 =====
VALID_TRANSITIONS = {
    "pending":     ["dispatched", "failed", "processing", "awaiting_dispatch"],
    "dispatched":  ["accepted", "rejected", "stale", "failed", "processing"],
    "accepted":    ["processing", "rejected", "failed"],
    "processing":  ["completed", "failed", "stale"],
    "completed":   ["verified", "failed", "dispatched"],
    "verified":    [],
    "rejected":    ["dispatched", "failed"],
    "stale":       ["dispatched", "failed", "accepted"],
    "failed":      ["dispatched", "pending"],
    "awaiting_dispatch": ["completed", "failed"],
}


def _validate_transition(current: str, target: str) -> bool:
    """校验状态流转合法性"""
    allowed = VALID_TRANSITIONS.get(current, [])
    return target in allowed


def _get_operator_id(db: Session, user_id: int) -> int | None:
    """根据登录用户获取操作员ID（优先 operator_id 直连）"""
    from ..models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    if user.operator_id:
        return user.operator_id
    op = db.query(Operator).filter(
        (Operator.name == user.display_name) | (func.instr(user.display_name, Operator.name) > 0)
    ).first()
    return op.id if op else None


def _get_operator_name(db: Session, operator_id: int) -> str:
    op = db.query(Operator).get(operator_id)
    return op.name if op else f"#{operator_id}"


# ===== 请求模型 =====
class DispatchRequest(BaseModel):
    decision_ids: list[str] | None = None  # 为空则从pending中批量派发

class UrgeRequest(BaseModel):
    decision_id: str

class ReassignRequest(BaseModel):
    decision_id: str
    operator_id: int

class BatchDispatchRequest(BaseModel):
    decision_ids: list[str]


# ===== 1. 管理员派单 =====
@router.post("/dispatch")
async def dispatch_tasks(
    req: DispatchRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """管理员派发待分配任务给操作员"""
    # 查询待派发且绑定操作员的分拣决策
    query = db.query(
        SortingDecision, OperatorChute
    ).join(
        OperatorChute, SortingDecision.target_chute == OperatorChute.chute_code
    ).filter(
        SortingDecision.status == "pending",
        OperatorChute.operator_id.isnot(None),
    )

    pending_decisions = query.all()
    if not pending_decisions:
        return {"code": 200, "message": "暂无待派发任务", "data": {"dispatched": 0}}

    dispatched_count = 0
    dispatched_list = []
    for decision, op_chute in pending_decisions:
        operator_id = op_chute.operator_id
        operator_name = _get_operator_name(db, operator_id)
        now = datetime.utcnow()

        # 创建派发记录
        assignment = TaskAssignment(
            assignment_id=_uuid.uuid4().hex,
            decision_id=decision.decision_id,
            file_id=decision.file_id,
            operator_id=operator_id,
            operator_name=operator_name,
            chute_code=decision.target_chute,
            status="dispatched",
            assigned_at=now,
        )
        db.add(assignment)

        # 更新决策状态
        decision.status = "dispatched"

        # 写入消息（操作员端可见）
        msg = MessageRecord(
            message_id=_uuid.uuid4().hex,
            category="task_dispatched",
            title=f"📦 新任务到达",
            content=f"包裹 {decision.tracking_number or '未知'} → {decision.target_chute}",
            level="info",
            target_role="operator",
            target_operator_id=operator_id,
            from_name="系统(派单)",
            from_role="system",
            related_tracking=decision.tracking_number,
            related_chute=decision.target_chute,
            related_decision_id=decision.decision_id,
        )
        db.add(msg)

        dispatched_count += 1
        task_data = {
            "file_id": decision.file_id,
            "decision_id": decision.decision_id,
            "tracking_number": decision.tracking_number,
            "target_chute": decision.target_chute,
            "province": decision.province,
            "city": decision.city,
            "district": decision.district,
            "operator_name": operator_name,
        }
        dispatched_list.append(task_data)

        # WebSocket推送
        background_tasks.add_task(ws_manager.broadcast_task_dispatched, operator_id, task_data)

    db.commit()

    return {
        "code": 200,
        "message": f"已派发 {dispatched_count} 个任务",
        "data": {"dispatched": dispatched_count, "tasks": dispatched_list},
    }


# ===== 2. 管理员催办 =====
@router.post("/urge")
async def urge_task(
    req: UrgeRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """管理员催办超时/滞留任务"""
    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "决策记录不存在")

    # 更新催办信息
    decision.urged_at = datetime.utcnow()
    decision.urge_count = (decision.urge_count or 0) + 1
    db.commit()

    # 查询该任务对应的操作员
    assignment = db.query(TaskAssignment).filter(
        TaskAssignment.decision_id == req.decision_id,
        TaskAssignment.status.in_(["dispatched", "accepted", "processing"]),
    ).order_by(TaskAssignment.assigned_at.desc()).first()

    if assignment:
        # 写入消息
        msg = MessageRecord(
            message_id=_uuid.uuid4().hex,
            category="task_urged",
            title=f"⚠️ 管理员催办",
            content=f"请尽快处理包裹 {decision.tracking_number or decision.file_id[:8]}",
            level="warning",
            target_role="operator",
            target_operator_id=assignment.operator_id,
            from_name="管理员",
            from_role="admin",
            related_tracking=decision.tracking_number,
            related_chute=decision.target_chute,
            related_decision_id=decision.decision_id,
        )
        db.add(msg)
        db.commit()

        background_tasks.add_task(
            ws_manager.broadcast_task_urged,
            assignment.operator_id, req.decision_id, decision.tracking_number or "",
        )

    return {"code": 200, "message": "催办已发送", "data": {
        "decision_id": req.decision_id,
        "urge_count": decision.urge_count,
    }}


# ===== 3. 管理员改派 =====
@router.post("/reassign")
async def reassign_task(
    req: ReassignRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """管理员将任务改派给其他操作员"""
    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "决策记录不存在")

    old_operator_id = None
    old_chute = decision.target_chute

    # 关闭旧的派发记录
    old_assignments = db.query(TaskAssignment).filter(
        TaskAssignment.decision_id == req.decision_id,
        TaskAssignment.status.in_(["dispatched", "accepted"]),
    ).all()
    for a in old_assignments:
        old_operator_id = a.operator_id
        a.status = "rejected"
        a.reject_reason = f"管理员改派至操作员#{req.operator_id}"

    now = datetime.utcnow()
    new_operator_name = _get_operator_name(db, req.operator_id)

    # 创建新的派发记录
    new_assignment = TaskAssignment(
        assignment_id=_uuid.uuid4().hex,
        decision_id=req.decision_id,
        file_id=decision.file_id,
        operator_id=req.operator_id,
        operator_name=new_operator_name,
        chute_code=decision.target_chute,
        status="dispatched",
        assigned_at=now,
    )
    db.add(new_assignment)

    # 如果决策状态是rejected/stale，重置为dispatched
    if decision.status in ("rejected", "stale"):
        decision.status = "dispatched"

    db.commit()

    task_data = {
        "file_id": decision.file_id,
        "decision_id": decision.decision_id,
        "tracking_number": decision.tracking_number,
        "target_chute": decision.target_chute,
        "operator_name": new_operator_name,
    }

    # 通知新操作员
    background_tasks.add_task(
        ws_manager.broadcast_task_reassigned,
        req.operator_id, req.decision_id, decision.target_chute or "", old_chute or "",
    )
    # 通知新操作员有任务到达
    background_tasks.add_task(
        ws_manager.broadcast_task_dispatched, req.operator_id, task_data
    )

    return {"code": 200, "message": f"已改派至 {new_operator_name}", "data": {
        "decision_id": req.decision_id,
        "new_operator_id": req.operator_id,
        "new_operator_name": new_operator_name,
    }}


# ===== 4. 批量派发（指定决策列表） =====
@router.post("/batch-dispatch")
async def batch_dispatch(
    req: BatchDispatchRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """批量派发指定任务"""
    dispatched_count = 0
    dispatched_list = []

    for decision_id in req.decision_ids:
        decision = db.query(SortingDecision).filter(
            SortingDecision.decision_id == decision_id,
            SortingDecision.status == "pending",
        ).first()
        if not decision:
            continue

        # 查询该分拣口绑定的操作员
        op_chute = db.query(OperatorChute).filter(
            OperatorChute.chute_code == decision.target_chute
        ).first()
        if not op_chute:
            continue

        operator_id = op_chute.operator_id
        operator_name = _get_operator_name(db, operator_id)
        now = datetime.utcnow()

        assignment = TaskAssignment(
            assignment_id=_uuid.uuid4().hex,
            decision_id=decision.decision_id,
            file_id=decision.file_id,
            operator_id=operator_id,
            operator_name=operator_name,
            chute_code=decision.target_chute,
            status="dispatched",
            assigned_at=now,
        )
        db.add(assignment)
        decision.status = "dispatched"

        task_data = {
            "file_id": decision.file_id,
            "decision_id": decision.decision_id,
            "tracking_number": decision.tracking_number,
            "target_chute": decision.target_chute,
            "operator_name": operator_name,
        }
        dispatched_list.append(task_data)
        background_tasks.add_task(ws_manager.broadcast_task_dispatched, operator_id, task_data)
        dispatched_count += 1

    db.commit()
    return {"code": 200, "message": f"已派发 {dispatched_count} 个任务", "data": {"dispatched": dispatched_count}}


# ===== 5. 自动派发（分拣引擎完成时自动调用） =====
def auto_dispatch_for_decision(decision_id: str, db: Session, background_tasks: BackgroundTasks) -> bool:
    """
    分拣决策完成后自动派发给操作员
    由 SortRuleEngine / sorting router 调用
    返回 True 表示成功派发
    """
    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == decision_id,
        SortingDecision.status == "pending",
    ).first()
    if not decision:
        return False

    op_chute = db.query(OperatorChute).filter(
        OperatorChute.chute_code == decision.target_chute
    ).first()
    if not op_chute:
        return False

    operator_id = op_chute.operator_id
    operator_name = _get_operator_name(db, operator_id)
    now = datetime.utcnow()

    assignment = TaskAssignment(
        assignment_id=_uuid.uuid4().hex,
        decision_id=decision.decision_id,
        file_id=decision.file_id,
        operator_id=operator_id,
        operator_name=operator_name,
        chute_code=decision.target_chute,
        status="dispatched",
        assigned_at=now,
    )
    db.add(assignment)
    decision.status = "dispatched"
    db.commit()

    task_data = {
        "file_id": decision.file_id,
        "decision_id": decision.decision_id,
        "tracking_number": decision.tracking_number,
        "target_chute": decision.target_chute,
        "operator_name": operator_name,
    }

    import asyncio
    asyncio.ensure_future(ws_manager.broadcast_task_dispatched(operator_id, task_data))

    print(f"[AutoDispatch] 自动派发 {decision.tracking_number} → {operator_name}")
    return True


# ===== 请求模型（追加） =====
class DirectProcessRequest(BaseModel):
    decision_id: str

class DirectCompleteRequest(BaseModel):
    decision_id: str


# ===== 6. 分拣员直接处理（跳过派发→接收→执行，直达处理中） =====
@router.post("/direct-process")
def direct_process(
    req: DirectProcessRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """分拣员对分拣口下的包裹一键开始处理（含幂等防护）"""
    operator_id = _get_operator_id(db, user_id)
    if not operator_id:
        raise HTTPException(400, "未找到操作员信息")
    operator_name = _get_operator_name(db, operator_id)

    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "任务不存在")

    # 幂等保护：已完成的不可再处理
    if decision.status in ("completed", "verified"):
        return {"code": 400, "message": "该包裹已被处理，无法重复操作", "data": {"status": decision.status}}

    # 校验分拣口归属
    op_chutes = db.query(OperatorChute).filter(
        OperatorChute.operator_id == operator_id
    ).all()
    my_chutes = [c.chute_code for c in op_chutes]
    if decision.target_chute not in my_chutes:
        raise HTTPException(403, f"该包裹属于{decision.target_chute}，不在您的管辖分拣口范围内")

    # 状态校验 & 流转
    if not _validate_transition(decision.status, "processing"):
        return {"code": 400, "message": f"当前状态{decision.status}不允许直接处理",
                "data": {"status": decision.status}}

    decision.status = "processing"
    now = datetime.utcnow()
    decision.handled_by = operator_id
    db.commit()

    # WebSocket推送
    task_data = {
        "decision_id": decision.decision_id,
        "tracking_number": decision.tracking_number,
        "target_chute": decision.target_chute,
        "operator_name": operator_name,
        "status": "processing",
    }
    background_tasks.add_task(ws_manager.broadcast_task_processing, operator_id, req.decision_id)

    return {"code": 200, "message": "已开始处理", "data": task_data}


# ===== 7. 分拣员直接完成（处理中→已完成，含幂等防护） =====
@router.post("/direct-complete")
def direct_complete(
    req: DirectCompleteRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """分拣员确认分拣完成"""
    operator_id = _get_operator_id(db, user_id)
    if not operator_id:
        raise HTTPException(400, "未找到操作员信息")
    operator_name = _get_operator_name(db, operator_id)

    decision = db.query(SortingDecision).filter(
        SortingDecision.decision_id == req.decision_id
    ).first()
    if not decision:
        raise HTTPException(404, "任务不存在")

    # 幂等保护
    if decision.status in ("completed", "verified"):
        return {"code": 400, "message": "该包裹已被处理，无法重复完成", "data": {"status": decision.status}}

    if not _validate_transition(decision.status, "completed"):
        return {"code": 400, "message": f"当前状态{decision.status}不允许标记完成"}

    now = datetime.utcnow()
    decision.status = "completed"
    decision.handled_at = now
    decision.handled_by = operator_id

    # 写 TaskAssignment 记录
    db.add(TaskAssignment(
        assignment_id=_uuid.uuid4().hex,
        decision_id=decision.decision_id,
        file_id=decision.file_id,
        operator_id=operator_id,
        operator_name=operator_name,
        chute_code=decision.target_chute,
        status="completed",
        assigned_at=decision.decision_time or now,
        completed_at=now,
    ))
    db.commit()

    background_tasks.add_task(
        ws_manager.broadcast_task_completed,
        operator_id, req.decision_id,
        decision.tracking_number or "", decision.target_chute or "",
    )

    return {"code": 200, "message": "分拣完成", "data": {
        "decision_id": req.decision_id,
        "tracking_number": decision.tracking_number,
        "target_chute": decision.target_chute,
        "operator_name": operator_name,
    }}


# ===== 8. 操作员申请发车（含3D装箱预览） =====
class BatchProcessRequest(BaseModel):
    decision_ids: list[str]


@router.post("/request-dispatch")
def request_dispatch(
    req: BatchProcessRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """操作员选包 → 3D装箱预览 → 向管理员申请发车"""
    operator_id = _get_operator_id(db, user_id)
    if not operator_id:
        raise HTTPException(400, "未找到操作员信息")
    operator_name = _get_operator_name(db, operator_id)
    if not req.decision_ids or len(req.decision_ids) < 1:
        raise HTTPException(400, "至少选择1个包裹")

    # 1. 收集包裹信息 + 标记为 awaiting_dispatch
    packed = []
    chutes = set()
    for did in req.decision_ids:
        d = db.query(SortingDecision).filter(SortingDecision.decision_id == did).first()
        if not d or d.status in ("verified", "awaiting_dispatch"):
            continue
        d.status = "awaiting_dispatch"
        d.handled_by = operator_id
        chutes.add(d.target_chute)
        from ..models.upload import UploadRecord
        up = db.query(UploadRecord).filter(UploadRecord.file_id == d.file_id).first()
        packed.append({
            "decision_id": did,
            "tracking": d.tracking_number or did[:12],
            "chute": d.target_chute,
            "district": d.district or "",
            "length": up.package_length or 30 if up else 30,
            "width": up.package_width or 20 if up else 20,
            "height": up.package_height or 15 if up else 15,
        })
    db.commit()

    if not packed:
        return {"code": 400, "message": "所选包裹均已被处理或已在申请中"}

    # 2. 3D装箱计算（缩小车厢：默认 200×100×150 cm；失败时降级）
    pack_result = {"fill_rate": 0, "placed_count": 0, "unplaced_count": len(packed), "total_volume": 0}
    try:
        from ..services.route_optimizer import RouteOptimizer
        bin_dims = (200, 100, 150)
        pkgs_for_bin = [{"id": i, "name": p["tracking"], "w": p["length"], "d": p["width"], "h": p["height"]}
                        for i, p in enumerate(packed)]
        if pkgs_for_bin:
            pack_result = RouteOptimizer.pack_bins(pkgs_for_bin, container_dims=bin_dims)
            pack_result["placed_count"] = pack_result.get("filled_packages", pack_result.get("valid_packages", len(packed)))
            pack_result["unplaced_count"] = max(0, len(packed) - pack_result.get("placed_count", 0))
    except Exception as e:
        print(f"[request-dispatch] pack failed: {e}")

    # 3. 写入消息通知管理员
    chute_list = ",".join(sorted(chutes)) if chutes else "未知"
    msg = MessageRecord(
        message_id=_uuid.uuid4().hex,
        category="dispatch_request",
        title=f"🚛 {operator_name} 申请发车",
        content=f"分拣口{chute_list}，{len(packed)}件包裹待审批发车",
        level="info",
        target_role="admin",
        from_user_id=user_id,
        from_name=operator_name,
        from_role="operator",
    )
    db.add(msg)
    db.commit()

    background_tasks.add_task(ws_manager.broadcast, "dashboard", {
        "event": "dispatch_requested",
        "data": {"operator": operator_name, "count": len(packed), "chutes": list(chutes),
                 "decision_ids": [p["decision_id"] for p in packed], "pack_result": pack_result}
    })

    return {"code": 200, "message": f"已申请发车{len(packed)}件，等待管理员审批",
            "data": {"count": len(packed), "chutes": list(chutes), "pack_result": pack_result}}


# ===== 9. 管理员获取待审批发车申请 =====
@router.get("/dispatch-requests")
def list_dispatch_requests(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """管理员查看所有 awaiting_dispatch，按操作员分组（一人多分拣口合并）"""
    decisions = db.query(SortingDecision).filter(
        SortingDecision.status == "awaiting_dispatch"
    ).all()

    # 预加载所有操作员，避免N+1查询
    op_ids = list(set(d.handled_by or 0 for d in decisions))
    op_map = {}
    if op_ids:
        ops = db.query(Operator).filter(Operator.id.in_(op_ids)).all()
        op_map = {o.id: o for o in ops}

    groups = {}
    for d in decisions:
        op_id = d.handled_by or 0
        if op_id not in groups:
            op = op_map.get(op_id)
            groups[op_id] = {"operator_id": op_id, "operator_name": op.name if op else "未知",
                             "count": 0, "decision_ids": [], "chutes": set(), "districts": []}
        groups[op_id]["count"] += 1
        groups[op_id]["decision_ids"].append(d.decision_id)
        if d.target_chute:
            groups[op_id]["chutes"].add(d.target_chute)
        if d.district:
            groups[op_id]["districts"].append(d.district)

    result = []
    for v in groups.values():
        v["chutes"] = sorted(v["chutes"])
        result.append(v)

    return {"code": 200, "data": {"requests": result, "total_awaiting": len(decisions)}}


# ===== 后台发车（ACO路径规划 + 创建车辆 + 启动模拟 + 通知） =====
def _dispatch_vehicle_background(completed_tns, notified_ops, districts):
    """后台线程执行ACO路径规划→创建车辆→启动模拟→广播通知"""
    from ..database import SessionLocal
    from ..services.route_optimizer import RouteOptimizer, PROV_GEO
    from ..services.delivery_tracking import haversine_km
    from ..websocket.manager import manager as ws_mgr
    import json as _json, asyncio

    db = SessionLocal()
    try:
        # 1. ACO路径优化
        dest_set = {}
        for district in districts:
            geo = PROV_GEO.get(district)
            if geo:
                dest_set[district] = {"id": len(dest_set)+1, "name": district, "lng": geo[0], "lat": geo[1], "demand": 5}

        waypoints = [{"lng": 115.8582, "lat": 28.6829, "name": "南昌分拣中心"}]
        if len(dest_set) >= 2:
            dests = list(dest_set.values())
            aco_result = RouteOptimizer.aco_route_real(dests, (115.8582, 28.6829), iterations=50, ants=15)
            for node in aco_result.get("path", []):
                if isinstance(node, dict) and node.get("name") != "南昌":
                    waypoints.append({"lng": node["lng"], "lat": node["lat"], "name": node["name"]})
        else:
            for d in dest_set.values():
                waypoints.append({"lng": d["lng"], "lat": d["lat"], "name": d["name"]})

        # 2. 计算总里程
        real_total = 0.0
        for i in range(1, len(waypoints)):
            real_total += haversine_km(waypoints[i-1]["lng"], waypoints[i-1]["lat"], waypoints[i]["lng"], waypoints[i]["lat"])

        speed = 20
        vehicle_id = f"V{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 3. 创建配送记录 + 车辆记录
        from ..models.logistics_records import DeliveryRecord, VehicleRecord
        for tn in completed_tns:
            db.add(DeliveryRecord(
                tracking_number=tn, vehicle_id=vehicle_id, origin="南昌",
                destination="南昌市", district="", node_status=1, node_status_name="分拣装车", active=1))
        db.add(VehicleRecord(
            vehicle_id=vehicle_id, waypoints_json=_json.dumps(waypoints, ensure_ascii=False),
            speed_kmh=speed, total_distance_km=round(real_total, 1),
            bound_packages=len(completed_tns), status="running"))
        db.commit()

        # 3.5 绑定包裹到内存追踪（小程序和物流追踪依赖此内存数据）
        from ..services.delivery_tracking import bind_packages_to_vehicle
        bind_packages_to_vehicle(completed_tns, vehicle_id)

        # 4. 启动车辆模拟
        from ..routers.logistics import start_vehicle_simulation
        start_vehicle_simulation(vehicle_id, waypoints, speed)

        # 5. 广播通知（在后台线程用asyncio异步发送）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(ws_mgr.broadcast("dashboard", {
                "event": "vehicle_departed",
                "data": {"vehicle_id": vehicle_id, "packages": len(completed_tns), "waypoints": waypoints}
            }))
            for op_id in notified_ops:
                loop.run_until_complete(ws_mgr.send_to_operator(op_id, {
                    "event": "dispatch_approved",
                    "data": {"vehicle_id": vehicle_id, "count": len(completed_tns), "waypoints": waypoints}
                }))
        finally:
            loop.close()

        print(f"[BG] 发车完成: {vehicle_id}, {len(completed_tns)}件, {len(waypoints)}站点, 里程{round(real_total,1)}km")

    except Exception as e:
        db.rollback()
        print(f"[BG] 发车失败: {e}")
    finally:
        db.close()


# ===== 10. 管理员审批发车（ACO路径规划 + 标记完成 + 发车 + 通知操作员） =====
class ApproveDispatchRequest(BaseModel):
    decision_ids: list[str]


@router.post("/approve-dispatch")
def approve_dispatch(
    req: ApproveDispatchRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """管理员审批发车：标记完成 → 立即响应 → 后台ACO+发车+通知"""
    if not req.decision_ids:
        raise HTTPException(400, "请选择至少一个申请")

    # 批量查询，避免N+1
    decisions = db.query(SortingDecision).filter(
        SortingDecision.decision_id.in_(req.decision_ids)
    ).all()

    completed_tns = []
    completed_ids = []
    notified_ops = set()
    districts = set()

    for d in decisions:
        if d.status in ("completed", "verified"):
            continue
        d.status = "completed"
        d.handled_at = datetime.utcnow()
        tn = d.tracking_number or d.file_id[:12]
        completed_tns.append(tn)
        completed_ids.append(d.decision_id)
        if d.handled_by:
            notified_ops.add(d.handled_by)
        if d.district:
            districts.add(d.district)
        db.add(TaskAssignment(
            assignment_id=_uuid.uuid4().hex, decision_id=d.decision_id, file_id=d.file_id,
            operator_id=d.handled_by or 0, operator_name="管理员审批",
            chute_code=d.target_chute, status="completed",
            assigned_at=d.decision_time or datetime.utcnow(), completed_at=datetime.utcnow(),
        ))

    if not completed_tns:
        return {"code": 400, "message": "所选申请均已被处理"}

    db.commit()

    # 后台异步：ACO路径优化 + 创建车辆 + 启动模拟 + 广播通知
    background_tasks.add_task(
        _dispatch_vehicle_background, completed_tns, notified_ops, list(districts)
    )

    return {"code": 200, "message": f"审批通过（{len(completed_tns)}件），后台发车中..."}
