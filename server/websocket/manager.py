import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for all active games."""

    def __init__(self):
        # game_id -> {player_id -> websocket}
        self.student_connections: dict[int, dict[int, WebSocket]] = {}
        # game_id -> websocket
        self.instructor_connections: dict[int, WebSocket] = {}

    async def connect_student(self, game_id: int, player_id: int, ws: WebSocket) -> None:
        await ws.accept()
        if game_id not in self.student_connections:
            self.student_connections[game_id] = {}
        self.student_connections[game_id][player_id] = ws

    async def connect_instructor(self, game_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self.instructor_connections[game_id] = ws

    def disconnect_student(self, game_id: int, player_id: int) -> None:
        if game_id in self.student_connections:
            self.student_connections[game_id].pop(player_id, None)

    def disconnect_instructor(self, game_id: int) -> None:
        self.instructor_connections.pop(game_id, None)

    async def send_to_student(self, game_id: int, player_id: int, data: dict[str, Any]) -> None:
        ws = self.student_connections.get(game_id, {}).get(player_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.disconnect_student(game_id, player_id)

    async def send_to_instructor(self, game_id: int, data: dict[str, Any]) -> None:
        ws = self.instructor_connections.get(game_id)
        if ws:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                self.disconnect_instructor(game_id)

    async def broadcast_to_students(self, game_id: int, data: dict[str, Any]) -> None:
        connections = self.student_connections.get(game_id, {})
        dead: list[int] = []
        for pid, ws in connections.items():
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(pid)
        for pid in dead:
            self.disconnect_student(game_id, pid)

    async def broadcast_to_all(self, game_id: int, data: dict[str, Any]) -> None:
        await self.broadcast_to_students(game_id, data)
        await self.send_to_instructor(game_id, data)

    def get_student_count(self, game_id: int) -> int:
        return len(self.student_connections.get(game_id, {}))

    def cleanup_game(self, game_id: int) -> None:
        self.student_connections.pop(game_id, None)
        self.instructor_connections.pop(game_id, None)


manager = ConnectionManager()
