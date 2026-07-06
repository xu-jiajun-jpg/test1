"""WebSocket 连接管理 — 支持分组广播 + 操作员个人通道 + 业务事件方法"""
from fastapi import WebSocket
from collections import defaultdict
import json


class ConnectionManager:
    """WebSocket 连接管理器 — 支持分组广播（dashboard / operator）"""

    def __init__(self):
        # group -> set of WebSocket
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        # 操作员个人通道：operator_id -> ws
        self._operator_sockets: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, group: str = "dashboard"):
        await websocket.accept()
        self._connections[group].add(websocket)
        print(f"[WS] +1 {group} (total: {len(self._connections[group])})")

    async def connect_operator(self, websocket: WebSocket, operator_id: int):
        """操作员专用连接"""
        await websocket.accept()
        self._operator_sockets[operator_id] = websocket
        self._connections["operator"].add(websocket)
        print(f"[WS] +1 operator#{operator_id} (total: {len(self._operator_sockets)})")

    def disconnect(self, websocket: WebSocket, group: str = "dashboard"):
        self._connections[group].discard(websocket)
        # 清理操作员映射
        for oid, ws in list(self._operator_sockets.items()):
            if ws is websocket:
                del self._operator_sockets[oid]
        print(f"[WS] -1 {group} (total: {len(self._connections[group])})")

    async def broadcast(self, group: str, message: dict):
        """向指定组所有客户端广播消息"""
        dead = set()
        for ws in self._connections.get(group, set()):
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[group].discard(ws)

    async def send_to_operator(self, operator_id: int, message: dict):
        """向指定操作员发送消息"""
        ws = self._operator_sockets.get(operator_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                del self._operator_sockets[operator_id]

    # ===== 原有业务事件广播（保持向后兼容） =====

    async def broadcast_sort_result(self, decision: dict):
        """广播分拣结果到实时大屏"""
        await self.broadcast("dashboard", {
            "event": "sorting_result",
            "data": decision,
        })

    async def broadcast_task_handled(self, tracking_number: str, target_chute: str, handler: str):
        """操作员已处理 → 大屏更新"""
        await self.broadcast("dashboard", {
            "event": "task_handled",
            "data": {
                "tracking_number": tracking_number,
                "target_chute": target_chute,
                "handler": handler,
            },
        })

    async def broadcast_exception(self, exception: dict):
        """操作员上报异常 → 大屏告警"""
        await self.broadcast("dashboard", {
            "event": "exception_raised",
            "data": exception,
        })

    async def notify_operator_new_task(self, operator_id: int, chute: str, count: int):
        """通知操作员有新包裹到达"""
        await self.send_to_operator(operator_id, {
            "event": "new_task",
            "data": {"chute": chute, "count": count},
        })

    async def notify_operator_command(self, operator_id: int, message: str):
        """向操作员发送管理员指令"""
        await self.send_to_operator(operator_id, {
            "event": "admin_command",
            "data": {"message": message},
        })

    # ===== 新增：9态任务生命周期事件 =====

    async def broadcast_task_dispatched(self, operator_id: int, task_data: dict):
        """管理员派发新任务 → 通知操作员"""
        await self.send_to_operator(operator_id, {
            "event": "task_dispatched",
            "data": task_data,
        })
        # 同时通知管理员大屏
        await self.broadcast("dashboard", {
            "event": "task_dispatched",
            "data": {**task_data, "operator_id": operator_id},
        })

    async def notify_task_accepted(self, operator_id: int, decision_id: str):
        """操作员接收任务 → 通知管理员大屏"""
        await self.broadcast("dashboard", {
            "event": "task_accepted",
            "data": {"decision_id": decision_id, "operator_id": operator_id},
        })

    async def notify_task_rejected(self, operator_id: int, decision_id: str, reason: str):
        """操作员拒收任务 → 通知管理员"""
        await self.broadcast("dashboard", {
            "event": "task_rejected",
            "data": {"decision_id": decision_id, "operator_id": operator_id, "reason": reason},
        })

    async def broadcast_task_processing(self, operator_id: int, decision_id: str):
        """操作员开始执行 → 通知管理员大屏"""
        await self.broadcast("dashboard", {
            "event": "task_processing",
            "data": {"decision_id": decision_id, "operator_id": operator_id},
        })

    async def broadcast_task_completed(self, operator_id: int, decision_id: str, tracking_number: str, target_chute: str):
        """操作员完成分拣 → 通知管理员大屏"""
        await self.broadcast("dashboard", {
            "event": "task_completed",
            "data": {
                "decision_id": decision_id, "operator_id": operator_id,
                "tracking_number": tracking_number, "target_chute": target_chute,
            },
        })

    async def broadcast_task_verified(self, decision_id: str, handler: str):
        """管理员核验通过 → 通知操作员"""
        await self.broadcast("operator", {
            "event": "task_verified",
            "data": {"decision_id": decision_id, "handler": handler},
        })
        await self.broadcast("dashboard", {
            "event": "task_verified",
            "data": {"decision_id": decision_id, "handler": handler},
        })

    async def broadcast_task_stale(self, decision_id: str, chute: str, overdue_minutes: int):
        """任务超时滞留 → 通知管理员大屏"""
        await self.broadcast("dashboard", {
            "event": "task_stale",
            "data": {
                "decision_id": decision_id, "chute": chute,
                "overdue_minutes": overdue_minutes,
            },
        })

    async def broadcast_task_urged(self, operator_id: int, decision_id: str, tracking_number: str):
        """管理员催办 → 通知指定操作员"""
        await self.send_to_operator(operator_id, {
            "event": "task_urged",
            "data": {"decision_id": decision_id, "tracking_number": tracking_number},
        })

    async def broadcast_task_reassigned(self, operator_id: int, decision_id: str, new_chute: str, old_chute: str):
        """管理员改派 → 通知该操作员"""
        await self.send_to_operator(operator_id, {
            "event": "task_reassigned",
            "data": {
                "decision_id": decision_id,
                "new_chute": new_chute,
                "old_chute": old_chute,
            },
        })
        await self.broadcast("dashboard", {
            "event": "task_reassigned",
            "data": {"decision_id": decision_id, "operator_id": operator_id, "new_chute": new_chute},
        })

    async def broadcast_status_sync(self, summary: dict):
        """全量状态快照同步（定时或手动触发）"""
        await self.broadcast("dashboard", {
            "event": "status_sync",
            "data": summary,
        })

    async def broadcast_new_message(self, target_role: str, target_operator_id: int, msg_data: dict):
        """新消息实时推送 — 通知目标角色"""
        event_data = {"event": "message_received", "data": msg_data}
        if target_operator_id and target_operator_id in self._operator_sockets:
            await self._send(self._operator_sockets[target_operator_id], event_data)
        if target_role in ("admin", "both"):
            await self.broadcast("dashboard", event_data)
        if target_role in ("operator", "both"):
            await self.broadcast("operator", event_data)


manager = ConnectionManager()
