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
    QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)


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


class ScoringAdjustmentWindow(QDialog):
    def __init__(self, api, parent: QWidget | None = None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Scoring Adjustment")
        self.resize(820, 540)

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
        self.close_btn = QPushButton("Close")
        self.save_btn.setDefault(True)
        btns.addWidget(self.reset_btn)
        btns.addWidget(self.flat_btn)
        btns.addWidget(self.linear_btn)
        btns.addStretch()
        btns.addWidget(self.save_btn)
        btns.addWidget(self.close_btn)

        root = QVBoxLayout(self)
        root.addWidget(self.hint)
        root.addWidget(self.editor, 1)
        root.addLayout(btns)

        self.reset_btn.clicked.connect(self._load_default)
        self.flat_btn.clicked.connect(self._preset_close)
        self.linear_btn.clicked.connect(self._preset_linear)
        self.save_btn.clicked.connect(self._save)
        self.close_btn.clicked.connect(self.close)

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
