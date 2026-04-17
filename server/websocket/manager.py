import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for all game sessions."""

    def __init__(self):
        # session_id -> {player_id -> websocket}
        self.student_connections: dict[int, dict[int, WebSocket]] = {}
        # session_id -> websocket
        self.instructor_connections: dict[int, WebSocket] = {}

    async def connect_student(self, session_id: int, player_id: int, ws: WebSocket) -> None:
        await ws.accept()
        if session_id not in self.student_connections:
            self.student_connections[session_id] = {}
        self.student_connections[session_id][player_id] = ws

    async def connect_instructor(self, session_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.instructor_connections[session_id] = ws

    def disconnect_student(self, session_id: int, player_id: int) -> None:
        if session_id in self.student_connections:
            self.student_connections[session_id].pop(player_id, None)

    def disconnect_instructor(self, session_id: int) -> None:
        self.instructor_connections.pop(session_id, None)

    async def send_to_student(self, session_id: int, player_id: int, data: dict[str, Any]) -> None:
        ws = self.student_connections.get(session_id, {}).get(player_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.disconnect_student(session_id, player_id)

    async def send_to_instructor(self, session_id: int, data: dict[str, Any]) -> None:
        ws = self.instructor_connections.get(session_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.disconnect_instructor(session_id)

    async def broadcast_to_students(self, session_id: int, data: dict[str, Any]) -> None:
        connections = self.student_connections.get(session_id, {})
        dead: list[int] = []
        for pid, ws in connections.items():
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(pid)
        for pid in dead:
            self.disconnect_student(session_id, pid)

    async def broadcast_to_all(self, session_id: int, data: dict[str, Any]) -> None:
        await self.broadcast_to_students(session_id, data)
        await self.send_to_instructor(session_id, data)

    def get_student_count(self, session_id: int) -> int:
        return len(self.student_connections.get(session_id, {}))

    def cleanup_session(self, session_id: int) -> None:
        self.student_connections.pop(session_id, None)
        self.instructor_connections.pop(session_id, None)


manager = ConnectionManager()
