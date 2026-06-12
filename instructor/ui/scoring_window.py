"""Scoring Adjustment window.

Lets the instructor reshape the per-question points curve by dragging
control points on a chart. X = fraction of question time remaining at the
moment of answering (100% = instant, 0% = buzzer). Y = points awarded.

Changes are persisted via the /api/settings/scoring endpoint; the server
caches the curve in-process so new values take effect on the next question.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from instructor.connection_settings import load as load_connection, save as save_connection
from instructor.core.topic_manager import TopicManager


POINTS_MAX = 1000
HANDLE_R = 8
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 70, 28, 28, 48

# Elimination marks are expressed in the engine as fraction of time *elapsed*.
# The chart's X axis is fraction of time *remaining*, so we flip them: 1 - elapsed.
DEFAULT_ELIMINATION_ELAPSED = (0.33, 0.66)
ELIMINATION_LABELS = ("1st wrong answer removed", "2nd wrong answer removed")
ELIM_MIN, ELIM_MAX = 0.02, 0.98
ELIM_MIN_GAP = 0.02
ELIM_GRAB_PX = 6


class CurveEditor(QWidget):
    """Interactive chart with draggable control points."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setMouseTracking(True)
        self._pts: list[list[float]] = []  # [[t, points], ...]
        self._drag_idx: int | None = None
        # Elimination marks stored as fraction of time *elapsed* (engine units),
        # always sorted ascending. Two values: 1st-wrong, 2nd-wrong.
        self._elim: list[float] = list(DEFAULT_ELIMINATION_ELAPSED)
        self._elim_drag: int | None = None

    # ── data ────────────────────────────────────────────────────────────

    def set_points(self, pts: list[tuple[float, float]]) -> None:
        self._pts = [[float(t), float(p)] for t, p in pts]
        self._pts.sort(key=lambda q: q[0])
        self.update()

    def get_points(self) -> list[tuple[float, int]]:
        return [(t, int(round(p))) for t, p in self._pts]

    def set_elimination_marks(self, marks: list[float] | tuple[float, ...]) -> None:
        vals = sorted(max(ELIM_MIN, min(ELIM_MAX, float(m))) for m in marks)
        if len(vals) >= 2:
            self._elim = [vals[0], vals[1]]
        self.update()

    def get_elimination_marks(self) -> list[float]:
        return list(self._elim)

    # ── coord transforms ────────────────────────────────────────────────

    def _plot_rect(self) -> QRectF:
        return QRectF(
            MARGIN_L, MARGIN_T,
            max(10, self.width() - MARGIN_L - MARGIN_R),
            max(10, self.height() - MARGIN_T - MARGIN_B),
        )

    def _to_px(self, t: float, pts: float) -> QPointF:
        r = self._plot_rect()
        x = r.left() + t * r.width()
        y = r.bottom() - (pts / POINTS_MAX) * r.height()
        return QPointF(x, y)

    def _from_px(self, pos: QPointF) -> tuple[float, float]:
        r = self._plot_rect()
        t = (pos.x() - r.left()) / r.width() if r.width() else 0
        p = (r.bottom() - pos.y()) / r.height() * POINTS_MAX if r.height() else 0
        return max(0.0, min(1.0, t)), max(0.0, min(float(POINTS_MAX), p))

    # ── painting ────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._plot_rect()

        p.fillRect(self.rect(), QColor("#0f172a"))
        p.setPen(QPen(QColor("#334155"), 1))
        p.drawRect(r)

        label_font = QFont("Segoe UI", 8)
        p.setFont(label_font)

        # Grid lines + tick labels (every 10%, every 100 points)
        for i in range(11):
            x = r.left() + i / 10 * r.width()
            p.setPen(QPen(QColor("#1e293b"), 1))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))
            if i % 2 == 0:
                p.setPen(QColor("#94a3b8"))
                p.drawText(QPointF(x - 14, r.bottom() + 16), f"{i * 10}%")

        for i in range(11):
            y = r.bottom() - i / 10 * r.height()
            p.setPen(QPen(QColor("#1e293b"), 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            if i % 2 == 0:
                p.setPen(QColor("#94a3b8"))
                p.drawText(QPointF(r.left() - 44, y + 4), f"{int(i / 10 * POINTS_MAX)}")

        # Axis titles
        p.setPen(QColor("#cbd5e1"))
        title_font = QFont("Segoe UI", 9)
        p.setFont(title_font)
        p.drawText(
            QPointF(r.center().x() - 90, r.bottom() + 36),
            "Time remaining when answered",
        )
        p.save()
        p.translate(16, r.center().y() + 48)
        p.rotate(-90)
        p.drawText(0, 0, "Points awarded")
        p.restore()

        # Elimination markers — draggable vertical sliders showing where wrong
        # answers get removed. Drawn before the curve so handles render on top.
        elim_label_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        for i, (elapsed, label) in enumerate(zip(self._elim, ELIMINATION_LABELS)):
            t = 1.0 - elapsed  # convert to "time remaining" axis
            x = r.left() + t * r.width()
            active = (i == self._elim_drag)
            line_color = QColor("#fbbf24") if active else QColor("#f87171")
            p.setPen(QPen(line_color, 1.6 if active else 1.4, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))

            # Triangular grip handles at top and bottom of the line.
            grip = QColor("#fbbf24") if active else QColor("#f87171")
            p.setPen(QPen(QColor("#0f172a"), 1))
            p.setBrush(QBrush(grip))
            top_tri = QPolygonF([
                QPointF(x - 6, r.top() - 2),
                QPointF(x + 6, r.top() - 2),
                QPointF(x, r.top() + 6),
            ])
            bot_tri = QPolygonF([
                QPointF(x - 6, r.bottom() + 2),
                QPointF(x + 6, r.bottom() + 2),
                QPointF(x, r.bottom() - 6),
            ])
            p.drawPolygon(top_tri)
            p.drawPolygon(bot_tri)

            # Percentage readout above the top grip.
            p.setFont(elim_label_font)
            p.setPen(QColor("#fde68a") if active else QColor("#fca5a5"))
            pct = f"{int(round(elapsed * 100))}%"
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(pct)
            tx = x - tw / 2
            tx = max(r.left() + 2, min(r.right() - tw - 2, tx))
            p.drawText(QPointF(tx, r.top() - 8), pct)

            # Rotated descriptive label running up the line.
            p.save()
            p.translate(x - 4, r.bottom() - 14)
            p.rotate(-90)
            p.drawText(0, 0, label)
            p.restore()

        if not self._pts:
            return

        # Curve — stroke only; explicitly clear the brush so drawPath doesn't
        # fill the closed polygon underneath the line.
        path = QPainterPath(self._to_px(*self._pts[0]))
        for t, pts in self._pts[1:]:
            path.lineTo(self._to_px(t, pts))
        p.setPen(QPen(QColor("#6366f1"), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # Handles + value labels
        handle_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        p.setFont(handle_font)
        fm = p.fontMetrics()
        for i, (t, pts) in enumerate(self._pts):
            c = self._to_px(t, pts)
            fill = QColor("#fbbf24") if i == self._drag_idx else QColor("#34d399")
            p.setBrush(QBrush(fill))
            p.setPen(QPen(QColor("#0f172a"), 2))
            p.drawEllipse(c, HANDLE_R, HANDLE_R)
            p.setPen(QColor("#e2e8f0"))
            text = f"{int(round(pts))}"
            tw = fm.horizontalAdvance(text)
            # Place label to the right of the handle, but flip to the left
            # if it would clip past the plot's right edge.
            lx = c.x() + 12
            if lx + tw > r.right() - 2:
                lx = c.x() - 12 - tw
            ly = c.y() - 10
            # Keep within plot vertically if a handle sits at the very top.
            if ly < r.top() + fm.ascent():
                ly = c.y() + fm.ascent() + 12
            p.drawText(QPointF(lx, ly), text)

    # ── mouse interaction ──────────────────────────────────────────────

    def _hit(self, pos: QPointF) -> int | None:
        for i, (t, pts) in enumerate(self._pts):
            if (self._to_px(t, pts) - pos).manhattanLength() <= HANDLE_R * 2 + 2:
                return i
        return None

    def _hit_elim(self, pos: QPointF) -> int | None:
        r = self._plot_rect()
        # Allow grabbing slightly outside the plot rect for the triangle grips.
        if pos.y() < r.top() - 10 or pos.y() > r.bottom() + 10:
            return None
        best_i, best_dx = None, ELIM_GRAB_PX + 1
        for i, elapsed in enumerate(self._elim):
            x = r.left() + (1.0 - elapsed) * r.width()
            dx = abs(pos.x() - x)
            if dx <= best_dx:
                best_dx = dx
                best_i = i
        return best_i

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        # Curve handles take priority over elimination sliders.
        idx = self._hit(ev.position())
        if idx is not None:
            self._drag_idx = idx
            self.update()
            return
        eidx = self._hit_elim(ev.position())
        if eidx is not None:
            self._elim_drag = eidx
            self.update()

    def mouseMoveEvent(self, ev):
        if self._drag_idx is not None:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            t, pts = self._from_px(ev.position())
            if self._drag_idx == 0:
                t = 0.0
            elif self._drag_idx == len(self._pts) - 1:
                t = 1.0
            else:
                lo = self._pts[self._drag_idx - 1][0] + 0.01
                hi = self._pts[self._drag_idx + 1][0] - 0.01
                t = max(lo, min(hi, t))
            self._pts[self._drag_idx] = [t, pts]
            self.update()
            return

        if self._elim_drag is not None:
            self.setCursor(Qt.CursorShape.SplitHCursor)
            r = self._plot_rect()
            t_remaining = (ev.position().x() - r.left()) / r.width() if r.width() else 0
            t_remaining = max(0.0, min(1.0, t_remaining))
            elapsed = 1.0 - t_remaining
            i = self._elim_drag
            other = self._elim[1 - i]
            if i == 0:
                # 1st mark must stay strictly less than 2nd.
                hi = other - ELIM_MIN_GAP
                elapsed = max(ELIM_MIN, min(hi, elapsed))
            else:
                lo = other + ELIM_MIN_GAP
                elapsed = max(lo, min(ELIM_MAX, elapsed))
            self._elim[i] = elapsed
            self.update()
            return

        # Idle hover — update cursor based on what's under the mouse.
        if self._hit(ev.position()) is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._hit_elim(ev.position()) is not None:
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, _ev):
        self._drag_idx = None
        self._elim_drag = None
        self.unsetCursor()
        self.update()


class ScoringPanel(QWidget):
    """Scoring curve + elimination-mark editor as an embeddable widget."""

    def __init__(self, api, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        self.hint = QLabel(
            "Drag the green handles to reshape how points are awarded. "
            "X = fraction of question time remaining when the student answered "
            "(100% = instant, 0% = buzzer). Y = points awarded. "
            "A flatter line keeps scores closer together. "
            "Drag the red dashed sliders to set when wrong answers are removed; "
            "they cannot cross each other."
        )
        self.hint.setStyleSheet("color: #94a3b8;")
        self.hint.setWordWrap(True)

        self.editor = CurveEditor(self)

        btns = QHBoxLayout()
        self.reset_btn = QPushButton("Reset to Default (√ curve)")
        self.flat_btn = QPushButton("Preset: Close Scores")
        self.linear_btn = QPushButton("Preset: Linear")
        self.save_btn = QPushButton("Save")
        self.save_btn.setDefault(True)
        btns.addWidget(self.reset_btn)
        btns.addWidget(self.flat_btn)
        btns.addWidget(self.linear_btn)
        btns.addStretch()
        btns.addWidget(self.save_btn)

        root = QVBoxLayout(self)
        root.addWidget(self.hint)
        root.addWidget(self.editor, 1)
        root.addLayout(btns)

        self.reset_btn.clicked.connect(self._load_default)
        self.flat_btn.clicked.connect(self._preset_close)
        self.linear_btn.clicked.connect(self._preset_linear)
        self.save_btn.clicked.connect(self._save)

        self._load_from_server()

    # ── data ────────────────────────────────────────────────────────────

    def _load_from_server(self):
        try:
            data = self.api.get_scoring()
            self.editor.set_points([(p["t"], p["points"]) for p in data["points"]])
        except Exception as e:
            QMessageBox.warning(self, "Load failed", f"Could not load scoring curve:\n{e}")
            self._load_default_curve()
        try:
            elim = self.api.get_elimination()
            self.editor.set_elimination_marks(elim["marks"])
        except Exception as e:
            QMessageBox.warning(
                self, "Load failed",
                f"Could not load elimination marks:\n{e}",
            )
            self.editor.set_elimination_marks([0.33, 0.66])

    def _load_default(self):
        self._load_default_curve()
        self.editor.set_elimination_marks([0.33, 0.66])

    def _load_default_curve(self):
        pts = [(t, round(100 + 900 * math.sqrt(t))) for t in (0, 0.25, 0.5, 0.75, 1.0)]
        self.editor.set_points(pts)

    def _preset_close(self):
        self.editor.set_points(
            [(0.0, 600), (0.25, 720), (0.5, 820), (0.75, 910), (1.0, 1000)]
        )

    def _preset_linear(self):
        self.editor.set_points(
            [(0.0, 100), (0.25, 325), (0.5, 550), (0.75, 775), (1.0, 1000)]
        )

    def _save(self):
        payload = [{"t": t, "points": p} for t, p in self.editor.get_points()]
        try:
            self.api.set_scoring(payload)
            self.api.set_elimination(self.editor.get_elimination_marks())
        except Exception as e:
            QMessageBox.warning(self, "Save failed", str(e))
            return
        QMessageBox.information(
            self, "Saved",
            "Scoring curve and elimination timing saved. "
            "Applies to the next question (no restart needed).",
        )


class ConnectionPanel(QWidget):
    """Server connection settings and account password management."""

    def __init__(self, api, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        settings = load_connection()

        # ── Server Connection ────────────────────────────────────────────
        server_box = QGroupBox("Server Connection")
        server_form = QFormLayout(server_box)
        self.host_edit = QLineEdit(settings["server_host"])
        self.host_edit.setPlaceholderText("e.g. 192.168.1.50 or rudi.local")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(settings["server_port"])
        server_form.addRow("Server Host:", self.host_edit)
        server_form.addRow("Server Port:", self.port_spin)

        self.save_server_btn = QPushButton("Save && Reconnect")
        self.save_server_btn.clicked.connect(self._save_server)
        self.server_status = QLabel("")
        self.server_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.save_server_btn)
        btn_row.addWidget(self.server_status)
        btn_row.addStretch()
        server_form.addRow("", btn_row)

        # ── Account ───────────────────────────────────────────────────────
        account_box = QGroupBox("Account")
        account_form = QFormLayout(account_box)

        username_label = QLabel(api.username or settings.get("username", ""))
        username_label.setStyleSheet("font-weight: bold; padding: 2px 0;")
        account_form.addRow("Username:", username_label)

        self.current_pass_edit = QLineEdit()
        self.current_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_pass_edit.setPlaceholderText("Current password")
        self.new_pass_edit = QLineEdit()
        self.new_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_pass_edit.setPlaceholderText("New password (min 4 characters)")
        account_form.addRow("Current Password:", self.current_pass_edit)
        account_form.addRow("New Password:", self.new_pass_edit)

        self.change_pass_btn = QPushButton("Change Password")
        self.change_pass_btn.clicked.connect(self._change_password)
        self.pass_status = QLabel("")
        self.pass_status.setStyleSheet("color: #94a3b8; font-size: 12px;")
        pass_btn_row = QHBoxLayout()
        pass_btn_row.addWidget(self.change_pass_btn)
        pass_btn_row.addWidget(self.pass_status)
        pass_btn_row.addStretch()
        account_form.addRow("", pass_btn_row)

        root = QVBoxLayout(self)
        root.addWidget(server_box)
        root.addWidget(account_box)
        root.addStretch()

    def _save_server(self):
        host = self.host_edit.text().strip()
        port = self.port_spin.value()
        if not host:
            QMessageBox.warning(self, "Validation", "Server host cannot be empty.")
            return
        save_connection(host, port)
        new_url = f"http://{host}:{port}"
        self.api.base_url = new_url
        self.api.client = self.api._make_client(new_url, self.api.token)
        self.server_status.setText(f"Saved. Now connecting to {new_url}")
        self.server_status.setStyleSheet("color: #34d399; font-size: 12px;")

    def _change_password(self):
        current = self.current_pass_edit.text()
        new = self.new_pass_edit.text()
        if not current or not new:
            self.pass_status.setText("Both fields are required.")
            self.pass_status.setStyleSheet("color: #E53935; font-size: 12px;")
            return
        try:
            self.api.change_password(current, new)
        except Exception as e:
            self.pass_status.setText(str(e))
            self.pass_status.setStyleSheet("color: #E53935; font-size: 12px;")
            return
        try:
            s = load_connection()
            save_connection(s["server_host"], s["server_port"])
        except Exception:
            pass
        self.current_pass_edit.clear()
        self.new_pass_edit.clear()
        self.pass_status.setText("Password changed.")
        self.pass_status.setStyleSheet("color: #34d399; font-size: 12px;")


class _AddUserDialog(QDialog):
    """Small dialog for creating a new user."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add User")
        self.setMinimumWidth(320)

        from PyQt6.QtWidgets import QComboBox, QDialogButtonBox
        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Unique login name")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Temporary password")
        self.role_combo = QComboBox()
        self.role_combo.addItems(["instructor", "admin"])
        form.addRow("Username:", self.username_edit)
        form.addRow("Password:", self.password_edit)
        form.addRow("Role:", self.role_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _on_accept(self):
        if not self.username_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Username cannot be empty.")
            return
        if len(self.password_edit.text()) < 4:
            QMessageBox.warning(self, "Validation", "Password must be at least 4 characters.")
            return
        self.accept()

    @property
    def username(self) -> str:
        return self.username_edit.text().strip()

    @property
    def password(self) -> str:
        return self.password_edit.text()

    @property
    def role(self) -> str:
        return self.role_combo.currentText()


class _ResetPasswordDialog(QDialog):
    """Small dialog for resetting another user's password."""

    def __init__(self, username: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Reset Password — {username}")
        self.setMinimumWidth(300)

        from PyQt6.QtWidgets import QDialogButtonBox
        form = QFormLayout()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("New temporary password")
        form.addRow("New Password:", self.password_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(buttons)

    def _on_accept(self):
        if len(self.password_edit.text()) < 4:
            QMessageBox.warning(self, "Validation", "Password must be at least 4 characters.")
            return
        self.accept()

    @property
    def password(self) -> str:
        return self.password_edit.text()


class ManageUsersPanel(QWidget):
    """Admin-only panel for listing, adding, toggling, and deleting users."""

    _COL_USERNAME = 0
    _COL_ROLE = 1
    _COL_STATUS = 2
    _COL_CREATED = 3
    _COL_ACTIONS = 4

    def __init__(self, api, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api

        top_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._load)
        self.add_btn = QPushButton("Add User")
        self.add_btn.clicked.connect(self._add_user)
        top_row.addWidget(refresh_btn)
        top_row.addStretch()
        top_row.addWidget(self.add_btn)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Username", "Role", "Status", "Created", "Actions"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            self._COL_USERNAME, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            self._COL_ROLE, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            self._COL_STATUS, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            self._COL_CREATED, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            self._COL_ACTIONS, QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 12px;")

        root = QVBoxLayout(self)
        root.addLayout(top_row)
        root.addWidget(self.table, 1)
        root.addWidget(self.status_label)

        self._load()

    def _load(self):
        try:
            users = self.api.list_users()
        except Exception as e:
            self.status_label.setText(f"Failed to load users: {e}")
            self.status_label.setStyleSheet("color: #E53935; font-size: 12px;")
            return
        self._populate(users)
        self.status_label.setText("")

    def _populate(self, users: list[dict]):
        self.table.setRowCount(len(users))
        for row, user in enumerate(users):
            username = user["username"]
            is_active = user.get("active", True)

            self.table.setItem(row, self._COL_USERNAME, QTableWidgetItem(username))
            self.table.setItem(row, self._COL_ROLE, QTableWidgetItem(user.get("role", "")))
            self.table.setItem(row, self._COL_STATUS,
                               QTableWidgetItem("Active" if is_active else "Disabled"))
            created = user.get("created_at", "")[:10]
            self.table.setItem(row, self._COL_CREATED, QTableWidgetItem(created))

            cell = QWidget()
            cell_layout = QHBoxLayout(cell)
            cell_layout.setContentsMargins(4, 2, 4, 2)
            cell_layout.setSpacing(6)

            toggle_btn = QPushButton("Disable" if is_active else "Enable")
            toggle_btn.setFixedWidth(64)
            toggle_btn.clicked.connect(
                lambda _, u=username, a=is_active: self._toggle_active(u, not a)
            )

            reset_btn = QPushButton("Reset PW")
            reset_btn.setFixedWidth(72)
            reset_btn.clicked.connect(lambda _, u=username: self._reset_password(u))

            del_btn = QPushButton("Delete")
            del_btn.setFixedWidth(56)
            del_btn.setStyleSheet("color: #C62828;")
            del_btn.clicked.connect(lambda _, u=username: self._delete_user(u))

            cell_layout.addWidget(toggle_btn)
            cell_layout.addWidget(reset_btn)
            cell_layout.addWidget(del_btn)
            cell_layout.addStretch()
            self.table.setCellWidget(row, self._COL_ACTIONS, cell)

        self.table.resizeRowsToContents()

    def _set_status(self, msg: str, ok: bool = True):
        color = "#34d399" if ok else "#E53935"
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _add_user(self):
        dlg = _AddUserDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.create_user(dlg.username, dlg.password, dlg.role)
        except Exception as e:
            self._set_status(str(e), ok=False)
            return
        self._set_status(f"User '{dlg.username}' created.")
        self._load()

    def _toggle_active(self, username: str, active: bool):
        action = "enable" if active else "disable"
        reply = QMessageBox.question(
            self, "Confirm",
            f"{'Enable' if active else 'Disable'} user '{username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.patch_user(username, active=active)
        except Exception as e:
            self._set_status(str(e), ok=False)
            return
        self._set_status(f"User '{username}' {'enabled' if active else 'disabled'}.")
        self._load()

    def _reset_password(self, username: str):
        dlg = _ResetPasswordDialog(username, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.reset_user_password(username, dlg.password)
        except Exception as e:
            self._set_status(str(e), ok=False)
            return
        self._set_status(f"Password reset for '{username}'.")

    def _delete_user(self, username: str):
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Permanently delete user '{username}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_user(username)
        except Exception as e:
            self._set_status(str(e), ok=False)
            return
        self._set_status(f"User '{username}' deleted.")
        self._load()


class SettingsWindow(QDialog):
    """Tabbed settings dialog: Topics + Scoring + Connection [+ Manage Users (admin)]."""

    TAB_TOPICS = 0
    TAB_SCORING = 1
    TAB_CONNECTION = 2
    TAB_MANAGE_USERS = 3

    def __init__(self, api, parent: QWidget | None = None, initial_tab: int = 0):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Settings")
        self.resize(900, 600)

        self.tabs = QTabWidget(self)
        self.topic_manager = TopicManager(api)
        self.scoring_panel = ScoringPanel(api)
        self.connection_panel = ConnectionPanel(api)
        self.tabs.addTab(self.topic_manager, "Topics")
        self.tabs.addTab(self.scoring_panel, "Scoring")
        self.tabs.addTab(self.connection_panel, "Connection")

        if getattr(api, "role", "") == "admin":
            self.manage_users_panel = ManageUsersPanel(api)
            self.tabs.addTab(self.manage_users_panel, "Manage Users")

        self.tabs.setCurrentIndex(initial_tab)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close_btn)

        root = QVBoxLayout(self)
        root.addWidget(self.tabs, 1)
        root.addLayout(bottom)

    def show_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index)
