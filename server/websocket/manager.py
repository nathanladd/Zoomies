import asyncio
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
        # Send to every student concurrently. Sequential awaits used to mean
        # one student on a slow phone connection (TCP send buffer full) would
        # stall every other send behind it — including the instructor, which
        # made the projection window lag noticeably during games.
        connections = self.student_connections.get(game_id, {})
        if not connections:
            return
        payload = json.dumps(data)
        items = list(connections.items())

        async def _send(pid: int, ws: WebSocket) -> int | None:
            try:
                await ws.send_text(payload)
                return None
            except Exception:
                return pid

        results = await asyncio.gather(
            *[_send(pid, ws) for pid, ws in items],
            return_exceptions=False,
        )
        for pid in results:
            if pid is not None:
                self.disconnect_student(game_id, pid)

    async def broadcast_to_all(self, game_id: int, data: dict[str, Any]) -> None:
        # Fan out to students and the instructor in parallel so the projector
        # (driven off the instructor socket) never has to wait for the slowest
        # student before it can update.
        await asyncio.gather(
            self.broadcast_to_students(game_id, data),
            self.send_to_instructor(game_id, data),
        )

    def get_student_count(self, game_id: int) -> int:
        return len(self.student_connections.get(game_id, {}))

    def cleanup_game(self, game_id: int) -> None:
        self.student_connections.pop(game_id, None)
        self.instructor_connections.pop(game_id, None)


manager = ConnectionManager()
