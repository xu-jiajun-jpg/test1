"""
车辆发车模拟 — 沿规划路径匀速行驶
支持实时位置推算、ETA计算、进度推送
"""
import time
import math
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VehicleState:
    vehicle_id: str
    waypoints: list  # [(lng, lat, name), ...]
    speed_kmh: float  # 行驶速度 km/h
    current_index: int = 0         # 当前目标点索引
    current_lng: float = 0
    current_lat: float = 0
    progress_percent: float = 0    # 整体进度 0-100
    eta_minutes: float = 0         # 预计剩余时间(分钟)
    total_distance_km: float = 0
    traveled_km: float = 0
    remaining_km: float = 0
    status: str = "idle"           # idle / running / idle（到达后回到idle）
    start_time: float = 0
    segment_start_time: float = 0
    segment_distance: float = 0
    trip_count: int = 0            # 累计行程次数


# 全局车辆状态存储
_active_vehicles: dict[str, VehicleState] = {}
_vehicle_threads: dict[str, threading.Thread] = {}

# 状态变更回调（外部模块注册，如router写DB）
_status_callbacks: list = []


def haversine(lng1, lat1, lng2, lat2):
    """计算两点间球面距离(km)"""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def interpolate(lng1, lat1, lng2, lat2, fraction: float):
    """线性插值两点间位置"""
    return (
        lng1 + (lng2 - lng1) * fraction,
        lat1 + (lat2 - lat1) * fraction,
    )


def calculate_eta(remaining_km: float, speed_kmh: float) -> float:
    """计算预计到达时间（分钟）"""
    if speed_kmh <= 0:
        return 0
    return (remaining_km / speed_kmh) * 60


def _simulate_vehicle(vehicle_id: str):
    """后台线程：模拟车辆沿路径行驶"""
    state = _active_vehicles.get(vehicle_id)
    if not state or len(state.waypoints) < 2:
        return

    state.status = "running"
    state.start_time = time.time()
    state.current_index = 0
    state.current_lng = state.waypoints[0][0]
    state.current_lat = state.waypoints[0][1]
    state.traveled_km = 0

    update_interval = 1.0  # 每秒更新一次位置

    while state.status == "running" and state.current_index < len(state.waypoints) - 1:
        wp_current = state.waypoints[state.current_index]
        wp_next = state.waypoints[state.current_index + 1]

        seg_dist = haversine(wp_current[0], wp_current[1], wp_next[0], wp_next[1])
        state.segment_distance = seg_dist

        # 该段行驶时间(秒)
        seg_duration = (seg_dist / state.speed_kmh) * 3600 if state.speed_kmh > 0 else 0
        if seg_duration <= 0:
            state.current_index += 1
            continue

        state.segment_start_time = time.time()
        elapsed = 0

        while elapsed < seg_duration and state.status == "running":
            time.sleep(update_interval)
            elapsed = time.time() - state.segment_start_time
            fraction = min(elapsed / seg_duration, 1.0)

            # 更新当前位置
            lng, lat = interpolate(wp_current[0], wp_current[1], wp_next[0], wp_next[1], fraction)
            state.current_lng = lng
            state.current_lat = lat

            # 计算进度和ETA
            # 总距离
            total_dist = state.total_distance_km
            # 已完成段的总距离
            completed_dist = 0
            for i in range(state.current_index):
                w1 = state.waypoints[i]
                w2 = state.waypoints[i + 1]
                completed_dist += haversine(w1[0], w1[1], w2[0], w2[1])
            completed_dist += seg_dist * fraction
            state.traveled_km = round(completed_dist, 2)

            if total_dist > 0:
                state.progress_percent = round(completed_dist / total_dist * 100, 1)

            state.remaining_km = round(total_dist - completed_dist, 2)
            state.eta_minutes = round(calculate_eta(state.remaining_km, state.speed_kmh), 1)

        if state.status == "running":
            state.current_index += 1

    # 到达终点 → 回到空闲状态，可再次发车
    if state.status == "running":
        state.status = "idle"
        state.trip_count += 1
        state.progress_percent = 100
        state.remaining_km = 0
        state.eta_minutes = 0
        state.traveled_km = state.total_distance_km
        if len(state.waypoints) > 0:
            state.current_lng = state.waypoints[-1][0]
            state.current_lat = state.waypoints[-1][1]
        _fire_callbacks(vehicle_id, "idle")


def start_vehicle(vehicle_id: str, waypoints: list, speed_kmh: float = 30) -> VehicleState:
    """启动/重新发车（空闲车辆可直接重新发车）"""
    existing = _active_vehicles.get(vehicle_id)

    # 如果已在运行中，先停
    if existing and existing.status == "running":
        existing.status = "idle"
        _fire_callbacks(vehicle_id, "idle")

    total_dist = 0
    for i in range(len(waypoints) - 1):
        total_dist += haversine(waypoints[i][0], waypoints[i][1],
                                waypoints[i+1][0], waypoints[i+1][1])

    if existing and existing.status == "idle":
        # 空闲车辆重新发车 — 复用对象保留历史
        state = existing
        state.waypoints = waypoints
        state.speed_kmh = speed_kmh
        state.total_distance_km = round(total_dist, 2)
        state.remaining_km = round(total_dist, 2)
        state.eta_minutes = round(calculate_eta(total_dist, speed_kmh), 1)
        state.progress_percent = 0
        state.traveled_km = 0
        state.current_index = 0
    else:
        state = VehicleState(
            vehicle_id=vehicle_id,
            waypoints=waypoints,
            speed_kmh=speed_kmh,
            total_distance_km=round(total_dist, 2),
            remaining_km=round(total_dist, 2),
            eta_minutes=round(calculate_eta(total_dist, speed_kmh), 1),
        )
    _active_vehicles[vehicle_id] = state

    t = threading.Thread(target=_simulate_vehicle, args=(vehicle_id,), daemon=True)
    _vehicle_threads[vehicle_id] = t
    t.start()

    return state


def stop_vehicle(vehicle_id: str):
    """停止车辆 → 回到空闲状态"""
    if vehicle_id in _active_vehicles:
        _active_vehicles[vehicle_id].status = "idle"
        _fire_callbacks(vehicle_id, "idle")


def list_all_vehicles() -> list:
    """获取所有车辆状态列表"""
    result = []
    for vid, state in _active_vehicles.items():
        result.append({
            "vehicle_id": state.vehicle_id,
            "current_lng": round(state.current_lng, 6),
            "current_lat": round(state.current_lat, 6),
            "progress_percent": state.progress_percent,
            "eta_minutes": state.eta_minutes,
            "total_distance_km": state.total_distance_km,
            "traveled_km": state.traveled_km,
            "remaining_km": state.remaining_km,
            "speed_kmh": state.speed_kmh,
            "status": state.status,
        })
    return result


def get_vehicle_state(vehicle_id: str) -> Optional[dict]:
    """获取车辆当前状态"""
    state = _active_vehicles.get(vehicle_id)
    if not state:
        return None
    return {
        "vehicle_id": state.vehicle_id,
        "current_lng": round(state.current_lng, 6),
        "current_lat": round(state.current_lat, 6),
        "current_index": state.current_index,
        "progress_percent": state.progress_percent,
        "eta_minutes": state.eta_minutes,
        "total_distance_km": state.total_distance_km,
        "traveled_km": state.traveled_km,
        "remaining_km": state.remaining_km,
        "speed_kmh": state.speed_kmh,
        "status": state.status,
    }


def list_idle_vehicles() -> list:
    """获取所有空闲车辆"""
    return [v for v in list_all_vehicles() if v["status"] == "idle"]


def register_status_callback(cb):
    """注册车辆状态变更回调 cb(vehicle_id, new_status)"""
    _status_callbacks.append(cb)


def _fire_callbacks(vehicle_id: str, new_status: str):
    for cb in _status_callbacks:
        try:
            cb(vehicle_id, new_status)
        except Exception:
            pass
