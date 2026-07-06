"""
配送追踪 — 包裹绑定车辆状态机 + 车辆位置模拟
发货地: 江西南昌（全局硬编码）
配送模式: 南昌市内各分区配送（5节点状态机）
"""
import time
import math
import threading
from dataclasses import dataclass, field
from typing import Optional
from ..config import ORIGIN_CITY, ORIGIN_LNG, ORIGIN_LAT


# ===== 运输节点（南昌区内配送5节点） =====
TRANSPORT_NODES = [
    "已揽收",           # 0
    "分拣装车",         # 1
    "出库配送",         # 2
    "区内到达",         # 3
    "已签收",           # 4
]


# ===== 车辆模拟状态 =====
@dataclass
class VehicleSimState:
    vehicle_id: str
    waypoints: list = field(default_factory=list)  # [{lng, lat, name}]
    speed_kmh: float = 40
    current_index: int = 0      # 当前目标路点索引
    current_lng: float = ORIGIN_LNG
    current_lat: float = ORIGIN_LAT
    traveled_km: float = 0
    total_distance_km: float = 0
    progress_percent: float = 0
    eta_minutes: float = 0
    status: str = "running"     # running / idle / arrived
    started_at: float = 0
    last_update: float = 0


_vehicle_states: dict[str, VehicleSimState] = {}
_vehicle_lock = threading.Lock()
_simulation_running = False


def haversine_km(lng1, lat1, lng2, lat2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def start_vehicle_simulation(vehicle_id: str, waypoints: list, speed_kmh: float):
    """启动车辆模拟线程"""
    global _simulation_running
    with _vehicle_lock:
        total_dist = 0
        for i in range(1, len(waypoints)):
            total_dist += haversine_km(
                waypoints[i-1]["lng"], waypoints[i-1]["lat"],
                waypoints[i]["lng"], waypoints[i]["lat"])
        state = VehicleSimState(
            vehicle_id=vehicle_id,
            waypoints=waypoints,
            speed_kmh=max(speed_kmh, 1),  # 最低 1 km/h 防止除零
            current_index=1,
            current_lng=waypoints[0]["lng"] if waypoints else ORIGIN_LNG,
            current_lat=waypoints[0]["lat"] if waypoints else ORIGIN_LAT,
            total_distance_km=round(max(total_dist, 0.1), 2),  # 最低 0.1 km
            started_at=time.time(),
            last_update=time.time(),
        )
        _vehicle_states[vehicle_id] = state

    # 发车后立即推进到"出库配送"节点
    advance_delivery_status(vehicle_id, 2)

    if not _simulation_running:
        _simulation_running = True
        t = threading.Thread(target=_run_simulation_loop, daemon=True)
        t.start()


def _run_simulation_loop():
    """后台匀速模拟所有运行中车辆"""
    while True:
        time.sleep(2)
        with _vehicle_lock:
            active = {vid: s for vid, s in _vehicle_states.items() if s.status == "running"}
        if not active:
            break
        now = time.time()
        completed = []
        for vid, state in active.items():
            elapsed_h = (now - state.last_update) / 3600
            state.last_update = now
            dist_moved = state.speed_kmh * elapsed_h
            # 移动到下一个路点
            while dist_moved > 0 and state.current_index < len(state.waypoints):
                target = state.waypoints[state.current_index]
                dist_to_target = haversine_km(state.current_lng, state.current_lat, target["lng"], target["lat"])
                if dist_moved >= dist_to_target:
                    dist_moved -= dist_to_target
                    state.traveled_km = round(state.traveled_km + dist_to_target, 2)
                    state.current_lng = target["lng"]
                    state.current_lat = target["lat"]
                    state.current_index += 1
                    # 通知配送状态
                    if state.current_index > 1:
                        advance_delivery_status(vid, min(state.current_index, 3))
                else:
                    ratio = dist_moved / dist_to_target
                    state.current_lng += (target["lng"] - state.current_lng) * ratio
                    state.current_lat += (target["lat"] - state.current_lat) * ratio
                    state.traveled_km = round(state.traveled_km + dist_moved, 2)
                    dist_moved = 0
            # 更新进度
            if state.total_distance_km > 0:
                state.progress_percent = round(min(state.traveled_km / state.total_distance_km * 100, 100), 1)
                remaining = state.total_distance_km - state.traveled_km
                state.eta_minutes = round(remaining / state.speed_kmh * 60, 1) if state.speed_kmh > 0 else 0
            # 同步ETA到所有绑定包裹
            update_vehicle_position(vid, state.current_lng, state.current_lat, state.eta_minutes)
            # 到达终点
            if state.current_index >= len(state.waypoints):
                state.status = "idle"
                state.progress_percent = 100
                state.eta_minutes = 0
                advance_delivery_status(vid, 3)
                completed.append(vid)
        # 标记已到达的从活跃中移除
        for vid in completed:
            if vid in _vehicle_states:
                _vehicle_states[vid].status = "idle"
    global _simulation_running
    _simulation_running = False


def get_vehicle_state(vehicle_id: str) -> Optional[dict]:
    """获取车辆实时状态"""
    with _vehicle_lock:
        state = _vehicle_states.get(vehicle_id)
        if not state:
            return None
        return {
            "vehicle_id": state.vehicle_id,
            "status": state.status,
            "current_lng": state.current_lng,
            "current_lat": state.current_lat,
            "speed_kmh": state.speed_kmh,
            "traveled_km": state.traveled_km,
            "remaining_km": round(state.total_distance_km - state.traveled_km, 2),
            "total_distance_km": state.total_distance_km,
            "progress_percent": state.progress_percent,
            "eta_minutes": state.eta_minutes,
        }


# ===== 绑定状态 =====
@dataclass
class BindingInfo:
    vehicle_id: str
    bound_at: float           # 绑定时间戳
    status: str = "bound"     # bound / in_transit / delivered


@dataclass
class PackageDelivery:
    tracking_number: str
    origin: str = ORIGIN_CITY
    origin_lng: float = ORIGIN_LNG
    origin_lat: float = ORIGIN_LAT
    bindings: list = field(default_factory=list)   # [BindingInfo, ...]
    active_vehicle: str = ""                        # 当前车辆ID
    node_status: int = 0
    destination: str = ""
    eta_minutes: float = 0
    update_time: float = 0
    history: list = field(default_factory=list)


# 全局存储
_deliveries: dict[str, PackageDelivery] = {}
_lock = threading.Lock()

# 配送状态回调（外部注册写DB）
_delivery_callbacks: list = []


def _now() -> float:
    return time.time()


# ===== 包裹绑定 =====

def bind_packages_to_vehicle(tracking_numbers: list, vehicle_id: str, destinations: dict = None) -> list:
    """将包裹绑定到指定车辆（双向关联），可选传入运单号→目的地映射"""
    results = []
    dest_map = destinations or {}
    with _lock:
        now = _now()
        for tn in tracking_numbers:
            if not tn:
                continue

            # 已签收的不再绑定
            if tn in _deliveries and _deliveries[tn].node_status >= 4:
                results.append({"tracking_number": tn, "bound": False, "reason": "已签收，不可重新绑定"})
                continue

            # 已在其他车辆运输中的
            if tn in _deliveries and _deliveries[tn].active_vehicle:
                existing_vid = _deliveries[tn].active_vehicle
                if existing_vid != vehicle_id:
                    results.append({"tracking_number": tn, "bound": False,
                                    "reason": f"已被车辆 {existing_vid} 绑定"})
                    continue

            # 创建或更新
            if tn not in _deliveries:
                _deliveries[tn] = PackageDelivery(tracking_number=tn, update_time=now)

            d = _deliveries[tn]
            d.active_vehicle = vehicle_id
            d.bindings.append(BindingInfo(vehicle_id=vehicle_id, bound_at=now))
            d.node_status = 1  # 分拣装车
            d.history.append(("分拣装车", now))
            d.update_time = now
            # 填充目的地（从OCR省份+城市拼接）
            if tn in dest_map and dest_map[tn]:
                d.destination = dest_map[tn]

            results.append({"tracking_number": tn, "bound": True, "vehicle_id": vehicle_id})

    return results


# ===== 查询 =====

def get_package_status(tracking_number: str) -> Optional[dict]:
    """查单个包裹"""
    d = _deliveries.get(tracking_number)
    if not d:
        return None
    return _build_response(d)


def get_vehicle_packages(vehicle_id: str) -> list:
    """查车辆上的所有包裹"""
    with _lock:
        return [_build_response(d) for d in _deliveries.values()
                if d.active_vehicle == vehicle_id]


def get_all_active_deliveries() -> list:
    """所有未签收包裹"""
    with _lock:
        return [_build_response(d) for d in _deliveries.values() if d.node_status < 4]


def get_binding_summary() -> dict:
    """绑定摘要统计"""
    with _lock:
        total = len(_deliveries)
        bound = sum(1 for d in _deliveries.values() if d.active_vehicle)
        in_transit = sum(1 for d in _deliveries.values() if d.node_status == 2)
        delivered = sum(1 for d in _deliveries.values() if d.node_status >= 4)
        by_vehicle = {}
        for d in _deliveries.values():
            vid = d.active_vehicle
            if vid:
                by_vehicle[vid] = by_vehicle.get(vid, 0) + 1
        return {
            "total_packages": total,
            "bound_packages": bound,
            "in_transit": in_transit,
            "delivered": delivered,
            "by_vehicle": [{"vehicle_id": k, "count": v} for k, v in by_vehicle.items()],
        }


# ===== 位保同步 =====

def update_vehicle_position(vehicle_id: str, lng: float, lat: float, eta: float):
    """车辆位置更新，同步到所有绑定包裹"""
    with _lock:
        for d in _deliveries.values():
            if d.active_vehicle == vehicle_id:
                d.eta_minutes = eta
                d.update_time = _now()
                if d.node_status < 2:
                    d.node_status = 2
                    d.history.append(("出库配送", _now()))
                    _fire_delivery_callback(d.tracking_number, 2, "出库配送")


def advance_delivery_status(vehicle_id: str, new_node: int):
    """推进所有绑定包裹的运输节点"""
    with _lock:
        now = _now()
        for d in _deliveries.values():
            if d.active_vehicle == vehicle_id and d.node_status < new_node:
                d.node_status = new_node
                d.update_time = now
                d.history.append((TRANSPORT_NODES[new_node], now))
                _fire_delivery_callback(d.tracking_number, new_node, TRANSPORT_NODES[new_node])


def _build_response(d: PackageDelivery) -> dict:
    return {
        "tracking_number": d.tracking_number,
        "origin": d.origin,
        "origin_lng": d.origin_lng,
        "origin_lat": d.origin_lat,
        "active_vehicle": d.active_vehicle,
        "destination": d.destination,
        "node_status_code": d.node_status,
        "node_status_name": TRANSPORT_NODES[d.node_status],
        "eta_minutes": d.eta_minutes,
        "bind_count": len(d.bindings),
        "vehicle_lng": ORIGIN_LNG if not d.active_vehicle else 0,
        "vehicle_lat": ORIGIN_LAT if not d.active_vehicle else 0,
        "history": [{"node": n, "time": t} for n, t in d.history],
    }


def register_delivery_callback(cb):
    """注册配送状态变更回调 cb(tracking_number, node_status, node_name)"""
    _delivery_callbacks.append(cb)


def _fire_delivery_callback(tracking_number: str, node_status: int, node_name: str):
    for cb in _delivery_callbacks:
        try:
            cb(tracking_number, node_status, node_name)
        except Exception:
            pass


def recover_active_deliveries():
    """服务器启动时从DB恢复活跃配送记录+车辆模拟到内存"""
    try:
        from ..database import SessionLocal
        from ..models.logistics_records import DeliveryRecord, VehicleRecord
        import json as _json
        db = SessionLocal()
        # 1. 恢复包裹配送记录
        active = db.query(DeliveryRecord).filter(DeliveryRecord.active == 1).all()
        recovered = 0
        for d in active:
            tn = d.tracking_number
            if tn and tn not in _deliveries:
                pkg = PackageDelivery(
                    tracking_number=tn,
                    origin=d.origin or ORIGIN_CITY,
                    destination=d.destination or "南昌市",
                    node_status=d.node_status or 1,
                )
                if d.vehicle_id:
                    pkg.active_vehicle = d.vehicle_id
                _deliveries[tn] = pkg
                recovered += 1
        print(f"[tracking] 从DB恢复 {recovered} 条活跃配送记录")
        # 2. 恢复运行中车辆并重启模拟
        vehicles = db.query(VehicleRecord).filter(VehicleRecord.status == "running").all()
        restarted = 0
        for v in vehicles:
            if v.vehicle_id in _vehicle_states:
                continue
            try:
                waypoints = _json.loads(v.waypoints_json) if v.waypoints_json else []
            except Exception:
                waypoints = []
            if not waypoints or len(waypoints) < 2:
                continue
            total_dist = 0
            for i in range(1, len(waypoints)):
                total_dist += haversine_km(
                    waypoints[i-1]["lng"], waypoints[i-1]["lat"],
                    waypoints[i]["lng"], waypoints[i]["lat"])
            state = VehicleSimState(
                vehicle_id=v.vehicle_id,
                waypoints=waypoints,
                speed_kmh=v.speed_kmh or 20,
                current_index=1,
                current_lng=waypoints[0]["lng"],
                current_lat=waypoints[0]["lat"],
                total_distance_km=round(max(total_dist, 0.1), 2),
                started_at=time.time(),
                last_update=time.time(),
            )
            _vehicle_states[v.vehicle_id] = state
            restarted += 1
        if restarted:
            global _simulation_running
            if not _simulation_running:
                _simulation_running = True
                t = threading.Thread(target=_run_simulation_loop, daemon=True)
                t.start()
            # 已发车车辆立即推进到"出库配送"
            for vid in _vehicle_states:
                advance_delivery_status(vid, 2)
            print(f"[tracking] 重启 {restarted} 辆车模拟，推进出库状态")
        db.close()
    except Exception as e:
        print(f"[tracking] 恢复配送记录失败: {e}")

