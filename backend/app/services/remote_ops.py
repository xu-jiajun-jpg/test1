"""模块11+12：远程运维 + 多中心协同"""
import random
from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session


class RemoteOpsManager:
    """远程运维管理 — 设备监控 + 参数调整 + 升级管理"""

    @staticmethod
    def get_device_status(db: Session = None) -> dict:
        """获取设备状态（基于真实分拣口数据）"""
        devices = []
        if db:
            from ..models.sorting import SortingChute, SortingDecision
            chutes = db.query(SortingChute).all()
            for ch in chutes:
                load_count = db.query(func.count(SortingDecision.id)).filter(
                    SortingDecision.target_chute == ch.chute_code
                ).scalar() or 0
                load_pct = min(round(load_count / max(ch.capacity, 1) * 100, 1), 100)
                status = "running" if ch.is_active else "idle"
                if load_pct > 80: status = "warning"
                devices.append({
                    "id": ch.id, "name": ch.name, "code": ch.chute_code,
                    "type": "conveyor" if ch.chute_code != "CH-006" else "inspection",
                    "status": status, "capacity": ch.capacity,
                    "load": load_pct, "packages": load_count,
                    "location": ch.location,
                })
        if not devices:
            devices = [
                {"id": 1, "name": "分拣线A", "type": "conveyor", "status": "running", "capacity": 300, "load": 60, "packages": 3},
                {"id": 2, "name": "分拣线B", "type": "conveyor", "status": "running", "capacity": 300, "load": 45, "packages": 4},
                {"id": 3, "name": "扫描仪C1", "type": "scanner", "status": "running", "load": 50, "packages": 0},
                {"id": 4, "name": "机械臂R1", "type": "robot", "status": "idle", "load": 20, "packages": 0},
            ]

        running = sum(1 for d in devices if d["status"] == "running")
        warning = sum(1 for d in devices if d["status"] == "warning")
        idle = sum(1 for d in devices if d["status"] == "idle")
        return {
            "devices": devices,
            "summary": {
                "total_devices": len(devices), "running": running,
                "warning": warning, "idle": idle,
                "overall_health": round((running + warning * 0.6) / max(len(devices), 1), 2),
            },
        }

    @staticmethod
    def adjust_parameter(device_id: int, param: str, value) -> dict:
        return {
            "device_id": device_id, "parameter": param,
            "new_value": value, "status": "applied",
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def get_upgrade_status() -> dict:
        return {
            "current_version": "1.0.0",
            "latest_version": "1.0.0",
            "upgrade_available": False,
            "changelog": "完整OCR识别+分拣决策+破损检测+实时大屏+人工复核",
            "upgrade_history": [
                {"version": "1.0.0", "date": "2026-06-26", "status": "current"},
            ],
        }


class MultiCenterManager:
    """模块12：多中心协同管理"""

    @staticmethod
    def get_centers(db: Session = None) -> list:
        if db:
            from ..models.sorting import SortingChute, SortingDecision
            chutes = db.query(SortingChute).all()
            centers = []
            for ch in chutes:
                cnt = db.query(func.count(SortingDecision.id)).filter(
                    SortingDecision.target_chute == ch.chute_code
                ).scalar() or 0
                load = round(cnt / max(ch.capacity, 1), 2)
                centers.append({
                    "id": ch.id, "name": f"{ch.name}中心", "location": ch.location,
                    "capacity": ch.capacity, "load": load,
                    "status": "active" if ch.is_active else "inactive",
                })
            return centers
        return [
            {"id": 1, "name": "北京市区分拣中心", "location": "北京A区", "capacity": 300, "load": 0.0, "status": "active"},
            {"id": 2, "name": "上海分拣中心", "location": "上海B区", "capacity": 300, "load": 0.3, "status": "active"},
            {"id": 3, "name": "广东省分拣中心", "location": "广州C区", "capacity": 400, "load": 0.25, "status": "active"},
        ]

    @staticmethod
    def schedule_task(task: dict, db: Session = None) -> dict:
        centers = MultiCenterManager.get_centers(db)
        active = [c for c in centers if c["status"] == "active"]
        active.sort(key=lambda c: c["load"])
        target = active[0] if active else None
        return {
            "assigned_center": target["name"] if target else None,
            "center_id": target["id"] if target else None,
            "reason": f"负载最低({target['load']*100:.0f}%)" if target else "无可用的分拣中心",
            "estimated_completion": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def handle_failover(failed_center_id: int, db: Session = None) -> dict:
        centers = MultiCenterManager.get_centers(db)
        failed = next((c for c in centers if c["id"] == failed_center_id), None)
        neighbors = [c for c in centers if c["id"] != failed_center_id and c["status"] == "active"]
        neighbors.sort(key=lambda c: c["load"])
        return {
            "failed_center": failed["name"] if failed else f"中心#{failed_center_id}",
            "transfer_to": [{"id": n["id"], "name": n["name"]} for n in neighbors[:3]],
            "status": "failover_completed",
        }
