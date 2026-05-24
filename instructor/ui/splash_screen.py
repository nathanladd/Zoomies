"""Startup splash dialog — shows connection progress and handles failure recovery."""

from __future__ import annotations

import sys
import time

import httpx
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from instructor.api_client import ApiClient
from instructor.connection_settings import load as load_connection, save as save_connection
from version import __version__


def _http_scheme(port: int) -> str:
    return "https" if port == 443 else "http"


class StartupDialog(QDialog):
    """Shows a startup log and handles connection/login before the main window opens.

    On success:  api_client is set and the dialog accepts.
    On failure:  an inline settings form and Retry/Quit buttons are revealed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Rudi v{__version__}")
        self.setMinimumWidth(560)
        # No close button — Quit button is the explicit exit path.
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self.api_client: ApiClient | None = None
        self.conn: dict = {}

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── log area ─────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(200)
        self._log.setFont(QFont("Courier New", 10))
        root.addWidget(self._log)

        # ── connection settings form (revealed on failure) ────────────────
        self._form_widget = QWidget()
        form = QFormLayout(self._form_widget)
        form.setContentsMargins(0, 4, 0, 0)
        self._host_edit = QLineEdit()
        self._port_edit = QLineEdit()
        self._user_edit = QLineEdit()
        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Server Host:", self._host_edit)
        form.addRow("Server Port:", self._port_edit)
        form.addRow("Username:", self._user_edit)
        form.addRow("Password:", self._pass_edit)
        self._form_widget.hide()
        root.addWidget(self._form_widget)

        # ── Retry / Quit buttons (revealed on failure) ────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._retry_btn = QPushButton("Retry")
        self._quit_btn = QPushButton("Quit")
        self._retry_btn.clicked.connect(self._on_retry)
        self._quit_btn.clicked.connect(lambda: sys.exit(0))
        btn_row.addWidget(self._retry_btn)
        btn_row.addWidget(self._quit_btn)
        self._btn_widget = QWidget()
        self._btn_widget.setLayout(btn_row)
        self._btn_widget.hide()
        root.addWidget(self._btn_widget)

        # Kick off the startup sequence once the event loop is running.
        QTimer.singleShot(0, self._start)

    # ── logging ──────────────────────────────────────────────────────────────

    def _log_line(self, text: str, color: str | None = None) -> None:
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(QColor(color))
        cursor.insertText(text + "\n", fmt)
        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()
        QApplication.processEvents()

    # ── startup sequence ─────────────────────────────────────────────────────

    def _start(self) -> None:
        self._attempt(load_connection())

    def _attempt(self, conn: dict) -> None:
        host = conn["server_host"]
        port = conn["server_port"]
        username = conn.get("username", "instructor")
        password = conn.get("password", "rudi")
        base_url = f"{_http_scheme(port)}://{host}:{port}"

        self._log_line(f"Rudi v{__version__} starting")
        self._log_line(f"Loading connection settings")
        self._log_line(f"  Host:     {host}:{port}")
        self._log_line(f"  Username: {username}")
        self._log_line(f"Connecting to {base_url} ...")

        if not self._check_reachable(host, port):
            self._log_line(f"  FAILED — no response from {base_url}", color="#E53935")
            self._log_line("Correct the settings below and click Retry.")
            self._show_form(conn)
            return

        self._log_line("  OK — server is reachable", color="#2E7D32")
        self._log_line(f"Authenticating as '{username}' ...")

        api = ApiClient(base_url=base_url)
        try:
            api.login(username, password)
        except Exception as exc:
            self._log_line(f"  FAILED — {exc}", color="#E53935")
            self._log_line("Correct the credentials below and click Retry.")
            api.close()
            self._show_form(conn)
            return

        try:
            save_connection(host, port, username, password)
        except Exception as exc:
            self._log_line(f"  Warning: could not save connection settings: {exc}", color="#F9A825")
        self._log_line("  OK — authenticated", color="#2E7D32")
        self._log_line("Ready.")

        self.api_client = api
        self.conn = conn
        QTimer.singleShot(400, self.accept)

    def _check_reachable(self, host: str, port: int, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        url = f"{_http_scheme(port)}://{host}:{port}/api/topics"
        while time.monotonic() < deadline:
            try:
                r = httpx.get(url, timeout=1.0)
                if r.status_code < 500:
                    return True
            except Exception:
                pass
            QApplication.processEvents()
            time.sleep(0.25)
        return False

    # ── settings form ────────────────────────────────────────────────────────

    def _show_form(self, conn: dict) -> None:
        self._host_edit.setText(conn.get("server_host", "localhost"))
        self._port_edit.setText(str(conn.get("server_port", 5000)))
        self._user_edit.setText(conn.get("username", "instructor"))
        self._pass_edit.clear()
        self._form_widget.show()
        self._btn_widget.show()
        self.adjustSize()

    def _on_retry(self) -> None:
        host = self._host_edit.text().strip()
        try:
            port = int(self._port_edit.text().strip())
        except ValueError:
            self._log_line("  ERROR: Port must be a number.", color="#E53935")
            return

        username = self._user_edit.text().strip()
        password = self._pass_edit.text()

        self._form_widget.hide()
        self._btn_widget.hide()
        self.adjustSize()
        self._log_line("─" * 44)

        self._attempt({
            "server_host": host,
            "server_port": port,
            "username": username,
            "password": password,
        })
