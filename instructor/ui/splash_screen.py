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
    """Shows a startup log, then prompts for credentials before the main window opens.

    Flow:
      1. Auto-connect to saved host/port.
      2a. Not reachable → show connection form + Retry.
      2b. Reachable, no users → show first-admin setup form.
      2c. Reachable, has users → show login form.
    Credentials are never saved to disk.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Rudi v{__version__}")
        self.setMinimumWidth(560)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self.api_client: ApiClient | None = None
        self._conn: dict = {}
        self._base_url: str = ""

        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── log area ──────────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(180)
        self._log.setFont(QFont("Courier New", 10))
        root.addWidget(self._log)

        # ── connection form (host/port) — shown when server unreachable ───────
        self._conn_widget = QWidget()
        conn_form = QFormLayout(self._conn_widget)
        conn_form.setContentsMargins(0, 4, 0, 0)
        self._host_edit = QLineEdit()
        self._port_edit = QLineEdit()
        conn_form.addRow("Server Host:", self._host_edit)
        conn_form.addRow("Server Port:", self._port_edit)
        self._conn_widget.hide()
        root.addWidget(self._conn_widget)

        # ── login form — shown when server is reachable and has users ─────────
        self._login_widget = QWidget()
        login_form = QFormLayout(self._login_widget)
        login_form.setContentsMargins(0, 4, 0, 0)
        self._user_edit = QLineEdit()
        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_edit.returnPressed.connect(self._on_login)
        login_form.addRow("Username:", self._user_edit)
        login_form.addRow("Password:", self._pass_edit)
        self._login_widget.hide()
        root.addWidget(self._login_widget)

        # ── setup form — shown on first run when no users exist ───────────────
        self._setup_widget = QWidget()
        setup_form = QFormLayout(self._setup_widget)
        setup_form.setContentsMargins(0, 4, 0, 0)
        self._setup_user_edit = QLineEdit()
        self._setup_pass_edit = QLineEdit()
        self._setup_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_confirm_edit = QLineEdit()
        self._setup_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_confirm_edit.returnPressed.connect(self._on_create_admin)
        setup_form.addRow("Admin Username:", self._setup_user_edit)
        setup_form.addRow("Password:", self._setup_pass_edit)
        setup_form.addRow("Confirm Password:", self._setup_confirm_edit)
        self._setup_widget.hide()
        root.addWidget(self._setup_widget)

        # ── button row ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._retry_btn = QPushButton("Retry")
        self._login_btn = QPushButton("Login")
        self._setup_btn = QPushButton("Create Account")
        self._quit_btn = QPushButton("Quit")
        self._retry_btn.clicked.connect(self._on_retry)
        self._login_btn.clicked.connect(self._on_login)
        self._setup_btn.clicked.connect(self._on_create_admin)
        self._quit_btn.clicked.connect(lambda: sys.exit(0))
        for btn in (self._retry_btn, self._login_btn, self._setup_btn, self._quit_btn):
            btn_row.addWidget(btn)
        self._btn_widget = QWidget()
        self._btn_widget.setLayout(btn_row)
        self._btn_widget.hide()
        root.addWidget(self._btn_widget)

        QTimer.singleShot(0, self._start)

    # ── logging ───────────────────────────────────────────────────────────────

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

    # ── form visibility helpers ───────────────────────────────────────────────

    def _hide_all(self) -> None:
        for w in (self._conn_widget, self._login_widget, self._setup_widget, self._btn_widget):
            w.hide()
        for b in (self._retry_btn, self._login_btn, self._setup_btn):
            b.hide()

    def _show_connection_form(self) -> None:
        self._hide_all()
        self._host_edit.setText(self._conn.get("server_host", "localhost"))
        self._port_edit.setText(str(self._conn.get("server_port", 5000)))
        self._conn_widget.show()
        self._retry_btn.show()
        self._btn_widget.show()
        self.adjustSize()

    def _show_login_form(self) -> None:
        self._hide_all()
        self._user_edit.clear()
        self._pass_edit.clear()
        self._login_widget.show()
        self._login_btn.show()
        self._btn_widget.show()
        self._user_edit.setFocus()
        self.adjustSize()

    def _show_setup_form(self) -> None:
        self._hide_all()
        self._setup_user_edit.clear()
        self._setup_pass_edit.clear()
        self._setup_confirm_edit.clear()
        self._setup_widget.show()
        self._setup_btn.show()
        self._btn_widget.show()
        self._setup_user_edit.setFocus()
        self.adjustSize()

    # ── startup sequence ──────────────────────────────────────────────────────

    def _start(self) -> None:
        self._conn = load_connection()
        self._attempt_connect()

    def _attempt_connect(self) -> None:
        host = self._conn["server_host"]
        port = self._conn["server_port"]
        self._base_url = f"{_http_scheme(port)}://{host}:{port}"

        self._log_line(f"Rudi v{__version__} starting")
        self._log_line(f"Connecting to {self._base_url} ...")

        if not self._check_reachable(host, port):
            self._log_line(f"  FAILED — no response from {self._base_url}", color="#E53935")
            self._log_line("Correct the server address below and click Retry.")
            self._show_connection_form()
            return

        self._log_line("  OK — server is reachable", color="#2E7D32")

        try:
            resp = httpx.get(f"{self._base_url}/api/auth/setup", timeout=5.0)
            setup_needed = resp.status_code == 200 and resp.json().get("setup_needed", False)
        except Exception:
            setup_needed = False

        if setup_needed:
            self._log_line("No user accounts found. Create an admin account to continue.")
            self._show_setup_form()
        else:
            self._show_login_form()

    def _check_reachable(self, host: str, port: int, timeout_s: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout_s
        url = f"{_http_scheme(port)}://{host}:{port}/api/version"
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

    # ── button handlers ───────────────────────────────────────────────────────

    def _on_retry(self) -> None:
        host = self._host_edit.text().strip()
        try:
            port = int(self._port_edit.text().strip())
        except ValueError:
            self._log_line("  ERROR: Port must be a number.", color="#E53935")
            return
        self._conn = {"server_host": host, "server_port": port}
        self._hide_all()
        self._log_line("─" * 44)
        self._attempt_connect()

    def _on_login(self) -> None:
        username = self._user_edit.text().strip()
        password = self._pass_edit.text()
        if not username:
            self._log_line("  ERROR: Username is required.", color="#E53935")
            return
        self._log_line(f"Authenticating as '{username}' ...")
        api = ApiClient(base_url=self._base_url)
        try:
            api.login(username, password)
        except Exception as exc:
            self._log_line(f"  FAILED — {exc}", color="#E53935")
            api.close()
            self._pass_edit.clear()
            self._pass_edit.setFocus()
            return
        self._finish(api)

    def _on_create_admin(self) -> None:
        username = self._setup_user_edit.text().strip()
        password = self._setup_pass_edit.text()
        confirm = self._setup_confirm_edit.text()
        if not username:
            self._log_line("  ERROR: Username is required.", color="#E53935")
            return
        if len(password) < 8:
            self._log_line("  ERROR: Password must be at least 8 characters.", color="#E53935")
            return
        if password != confirm:
            self._log_line("  ERROR: Passwords do not match.", color="#E53935")
            self._setup_confirm_edit.clear()
            self._setup_confirm_edit.setFocus()
            return
        self._log_line(f"Creating admin account '{username}' ...")
        try:
            resp = httpx.post(
                f"{self._base_url}/api/auth/setup",
                json={"username": username, "password": password},
                timeout=8.0,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            self._log_line(f"  FAILED — {exc}", color="#E53935")
            return
        self._log_line("  OK — admin account created", color="#2E7D32")
        api = ApiClient(base_url=self._base_url)
        api.token = data["token"]
        api.role = data.get("role", "admin")
        api.username = data.get("username", username)
        api.set_token(data["token"])
        self._finish(api)

    def _finish(self, api: ApiClient) -> None:
        try:
            save_connection(self._conn["server_host"], self._conn["server_port"])
        except Exception as exc:
            self._log_line(f"  Warning: could not save connection settings: {exc}", color="#F9A825")
        self._log_line("  OK — authenticated", color="#2E7D32")
        self._log_line("Ready.")
        self.api_client = api
        QTimer.singleShot(400, self.accept)
