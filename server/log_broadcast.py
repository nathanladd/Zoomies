"""Capture server stdout/stderr and broadcast lines to WebSocket clients."""
from __future__ import annotations

import asyncio
import io
import logging
import sys
from typing import TextIO

from fastapi import WebSocket, WebSocketDisconnect


class LogBroadcaster:
    """Thread-safe log broadcaster that captures print() output and uvicorn
    logs, then fans them out to any connected ``/ws/logs`` WebSocket clients."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._original_stdout: TextIO | None = None
        self._original_stderr: TextIO | None = None

    # ── stdout/stderr capture ────────────────────────────────────────────

    def install(self) -> None:
        """Replace sys.stdout and sys.stderr with capturing wrappers."""
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = _CapturingStream(self, self._original_stdout)  # type: ignore[assignment]
        sys.stderr = _CapturingStream(self, self._original_stderr)  # type: ignore[assignment]

        # Also capture uvicorn / FastAPI loggers that go through logging
        handler = _BroadcastLogHandler(self)
        handler.setFormatter(logging.Formatter("%(message)s"))
        for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
            logger = logging.getLogger(name)
            logger.addHandler(handler)
            logger.propagate = False

    # ── client management ────────────────────────────────────────────────

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        await ws.send_text("=== Rudi server log connected ===")

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    # ── broadcasting ─────────────────────────────────────────────────────

    def broadcast_sync(self, line: str) -> None:
        """Called from synchronous code (print).  Schedules the async send."""
        stripped = line.rstrip()
        if not stripped:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._broadcast(stripped))
        except RuntimeError:
            pass  # no event loop yet (startup)

    async def _broadcast(self, line: str) -> None:
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in self._clients:
                try:
                    await ws.send_text(line)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._clients.discard(ws)


class _CapturingStream(io.TextIOBase):
    """Wraps an original stream; every write() is also broadcast."""

    def __init__(self, broadcaster: LogBroadcaster, original: TextIO) -> None:
        self._broadcaster = broadcaster
        self._original = original

    def write(self, s: str) -> int:  # type: ignore[override]
        if s and s.strip():
            self._broadcaster.broadcast_sync(s)
        return self._original.write(s)

    def flush(self) -> None:
        self._original.flush()

    def fileno(self) -> int:
        return self._original.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._original, "encoding", "utf-8")


class _BroadcastLogHandler(logging.Handler):
    """Logging handler that forwards formatted records to the broadcaster."""

    def __init__(self, broadcaster: LogBroadcaster) -> None:
        super().__init__()
        self._broadcaster = broadcaster

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._broadcaster.broadcast_sync(msg)
        except Exception:
            pass


# Module-level singleton
broadcaster = LogBroadcaster()
