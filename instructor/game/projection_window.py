from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QSizePolicy, QSplitter,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QKeyEvent, QPixmap, QMouseEvent

from version import __version__


class ProjectionWindow(QWidget):
    """Fullscreen projection display for Rudi games.

    Shows question text, optional image, timer, answer count, and leaderboard.
    Answer choices are NOT shown here — students see them on their own devices.
    """

    def __init__(self, game_id: int | None = None, server_host: str = "localhost", server_port: int = 5000):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.game_id = game_id
        self.server_host = server_host
        self.server_port = server_port
        self.setWindowTitle(f"Rudi v{__version__} — Projection")
        self.setMinimumSize(1024, 700)
        self.setStyleSheet("background-color: #0f172a; color: white;")

        self._is_waiting = False
        self._join_url = ""
        self._player_count = 0
        self._player_names: list[str] = []
        self._drag_pos = None
        self._build_ui()
        self._build_fullscreen_hint()
        self._build_version_label()
        self._show_waiting()
        self._place_hint()

    # ── Frameless window dragging ──────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not self.isFullScreen():
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Toggle fullscreen with F11 or Escape to exit fullscreen."""
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
            self._place_hint()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
            self._place_hint()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_hint()

    def closeEvent(self, event):
        """Hide instead of destroying.

        The control panel keeps this window alive for the whole session so
        its state (leaderboard, current question, timer, etc.) stays in sync
        with game play regardless of visibility. When the instructor "closes"
        it, we just hide; the window can be re-shown later and will already
        be up to date.
        """
        event.ignore()
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self._place_hint()

    # ── Fullscreen hint overlay ─────────────────────────────────────

    def _build_fullscreen_hint(self):
        self.fullscreen_hint = QLabel(
            "Press F11 for fullscreen  ·  Esc to exit", self,
        )
        self.fullscreen_hint.setStyleSheet(
            "color: #475569; background: transparent; font-size: 11px;"
        )
        self.fullscreen_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.fullscreen_hint.adjustSize()

    def _place_hint(self):
        if not hasattr(self, "fullscreen_hint"):
            return
        margin = 10
        self.fullscreen_hint.adjustSize()
        x = self.width() - self.fullscreen_hint.width() - margin
        y = self.height() - self.fullscreen_hint.height() - margin
        self.fullscreen_hint.move(max(0, x), max(0, y))
        self.fullscreen_hint.setVisible(not self.isFullScreen())
        self.fullscreen_hint.raise_()
        self._place_version_label()

    # ── Version label overlay ─────────────────────────────────────

    def _build_version_label(self):
        self.version_label = QLabel(f"v{__version__}", self)
        self.version_label.setStyleSheet(
            "color: #475569; background: transparent; font-size: 11px;"
        )
        self.version_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.version_label.adjustSize()

    def _place_version_label(self):
        if not hasattr(self, "version_label"):
            return
        margin = 10
        self.version_label.adjustSize()
        self.version_label.move(margin, self.height() - self.version_label.height() - margin)
        self.version_label.raise_()

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 20)
        self.main_layout.setSpacing(12)

        # ── Header row ─────────────────────────────────────────────────────
        header = QHBoxLayout()
        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Segoe UI", 18))
        self.progress_label.setStyleSheet("color: #94a3b8;")

        self.points_label = QLabel("")
        self.points_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.points_label.setStyleSheet("color: #34d399;")
        self.points_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        header.addWidget(self.progress_label)
        header.addStretch()
        header.addWidget(self.points_label)
        self.main_layout.addLayout(header)

        # ── Timer bar ──────────────────────────────────────────────────────
        self.timer_bar = QProgressBar()
        self.timer_bar.setMaximum(1000)
        self.timer_bar.setValue(1000)
        self.timer_bar.setTextVisible(False)
        self.timer_bar.setMaximumHeight(14)
        self.timer_bar.setStyleSheet("""
            QProgressBar {
                background-color: #334155;
                border-radius: 7px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #10b981);
                border-radius: 7px;
            }
        """)
        self.main_layout.addWidget(self.timer_bar)

        # ── Question text (large, centered) ────────────────────────────────
        self.question_label = QLabel("")
        self.question_label.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("color: #e2e8f0; padding: 24px;")
        self.question_label.setMinimumHeight(120)
        self.main_layout.addWidget(self.question_label)

        # ── Question image ─────────────────────────────────────────────────
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("padding: 8px;")
        self.image_label.hide()
        self.main_layout.addWidget(self.image_label)

        # ── Footer info row ────────────────────────────────────────────────
        footer = QHBoxLayout()
        self.answers_label = QLabel("")
        self.answers_label.setFont(QFont("Segoe UI", 16))
        self.answers_label.setStyleSheet("color: #94a3b8;")
        self.answers_label.setTextFormat(Qt.TextFormat.RichText)
        self.answers_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_text = QLabel("")
        self.timer_text.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        self.timer_text.setStyleSheet("color: #fbbf24;")
        self.timer_text.setAlignment(Qt.AlignmentFlag.AlignRight)
        footer.addWidget(self.answers_label)
        footer.addStretch()
        footer.addWidget(self.timer_text)
        self.main_layout.addLayout(footer)

        # ── Correct answer reveal label ────────────────────────────────────
        self.correct_label = QLabel("")
        self.correct_label.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.correct_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.correct_label.setStyleSheet(
            "color: #10b981; background-color: #064e3b; border-radius: 12px; padding: 16px;"
        )
        self.correct_label.hide()
        self.main_layout.addWidget(self.correct_label)

        # ── Leaderboard area ──────────────────────────────────────────────
        self.lb_title = QLabel("")
        self.lb_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lb_title.setStyleSheet("color: #818cf8; padding-top: 8px;")
        self.lb_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lb_title.hide()
        self.main_layout.addWidget(self.lb_title)

        self.leaderboard_widget = QWidget()
        self.lb_layout = QVBoxLayout(self.leaderboard_widget)
        self.lb_layout.setSpacing(2)
        self.leaderboard_widget.hide()
        self.main_layout.addWidget(self.leaderboard_widget)

        self.main_layout.addStretch()

    # ── Screen states ──────────────────────────────────────────────────────

    def _show_waiting(self):
        self._is_waiting = True
        self._player_count = 0
        self._player_names = []
        self.progress_label.setText("")
        self.points_label.setText("")
        self.timer_bar.hide()
        self.timer_text.setText("")
        self.answers_label.setText("")
        self.image_label.hide()
        self.correct_label.hide()
        self.lb_title.hide()
        self.leaderboard_widget.hide()

        self._join_url = f"{self.server_host}:{self.server_port}"

        self.question_label.setTextFormat(Qt.TextFormat.RichText)
        self.question_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._update_waiting_display()

    def _update_waiting_display(self):
        game_text = f"Game Number:&nbsp;&nbsp;<b>{self.game_id}</b>" if self.game_id else ""
        if self._player_count > 0:
            players_text = f'{self._player_count} player{"s" if self._player_count != 1 else ""} joined'
        else:
            players_text = "Waiting for players..."
        # Build player name list
        names_html = ""
        if self._player_names:
            name_spans = "&nbsp;&nbsp;&bull;&nbsp;&nbsp;".join(
                f'<span style="color:#e2e8f0;">{n}</span>' for n in self._player_names
            )
            names_html = (
                f'<div style="font-size:20px; color:#94a3b8; margin-top:16px; '
                f'line-height:1.6;">{name_spans}</div>'
            )
        self.question_label.setText(
            f'<div style="text-align:center;">'
            f'<div style="font-size:64px; font-weight:bold; color:#818cf8; margin-bottom:12px; letter-spacing:2px;">RUDI</div>'
            f'<div style="font-size:18px; font-style:italic; color:#cbd5e1; margin-bottom:6px; line-height:1.4;">'
            f'Named for Rudolf Christian Karl Diesel &mdash.'
            f'</div>'
            f'<div style="font-size:15px; color:#94a3b8; margin-bottom:14px;">A classroom quiz game.</div>'
            f'<div style="font-size:17px; font-style:italic; color:#fbbf24; margin-bottom:24px;">'
            f'&ldquo;Do not fear failure, but rather fear not trying at all.&rdquo; &mdash; Rudolf Diesel'
            f'</div>'
            f'<div style="font-size:20px; color:#94a3b8; margin-bottom:4px;">Join at</div>'
            f'<div style="font-size:40px; font-weight:bold; color:#818cf8; margin-bottom:16px;">{self._join_url}</div>'
            f'<div style="font-size:32px; font-weight:bold; color:#34d399; margin-bottom:16px;">{game_text}</div>'
            f'<div style="font-size:22px; color:#94a3b8;">{players_text}</div>'
            f'{names_html}'
            f'</div>'
        )

    def reset_for_new_game(self, game_id: int | None) -> None:
        """Refresh this projection window to advertise a new game.

        Called when the instructor starts a new game while this window is
        already open — we don't want to destroy/recreate the window (that
        loses fullscreen state and flashes a new window on the projector),
        we just snap back to the waiting screen with the new game number.
        """
        self.game_id = game_id
        self.question_label.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        self.question_label.setStyleSheet("color: #e2e8f0; padding: 24px;")
        self._show_waiting()

    # ── Event handlers called by the control panel ─────────────────────────

    def on_player_joined(self, msg: dict):
        self._player_count = msg.get('player_count', 0)
        name = msg.get('name', '')
        if name and name not in self._player_names:
            self._player_names.append(name)
        if self._is_waiting:
            self._update_waiting_display()
        else:
            self.answers_label.setText(f"{self._player_count} players joined")

    def on_game_start(self, msg: dict):
        self._is_waiting = False
        self.question_label.setTextFormat(Qt.TextFormat.PlainText)
        self.question_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.question_label.setMinimumHeight(120)
        self.question_label.setText("Get Ready!")
        self.question_label.setFont(QFont("Segoe UI", 40, QFont.Weight.Bold))
        self.question_label.setStyleSheet("color: #e2e8f0; padding: 20px;")

    def on_question_start(self, msg: dict):
        self.timer_bar.show()
        self.timer_bar.setValue(1000)
        self.leaderboard_widget.hide()
        self.lb_title.hide()
        self.correct_label.hide()

        idx = msg.get("index", 0)
        total = msg.get("total", 0)
        self.progress_label.setText(f"Question {idx + 1} of {total}")
        self.points_label.setText(f"{msg.get('max_points', 1000)} points")

        self.question_label.setText(msg.get("text") or "")
        self.question_label.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        self.question_label.setStyleSheet("color: #e2e8f0; padding: 24px;")

        # Show image if provided (fetched from the remote server over HTTP)
        image_url = msg.get("image_url")
        if image_url:
            try:
                import httpx
                url = f"http://{self.server_host}:{self.server_port}/{image_url.lstrip('/')}"
                resp = httpx.get(url, timeout=5.0)
                if resp.status_code == 200:
                    pixmap = QPixmap()
                    pixmap.loadFromData(resp.content)
                    if not pixmap.isNull():
                        scaled = pixmap.scaledToHeight(
                            min(350, pixmap.height()),
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self.image_label.setPixmap(scaled)
                        self.image_label.show()
                    else:
                        self.image_label.hide()
                else:
                    self.image_label.hide()
            except Exception:
                self.image_label.hide()
        else:
            self.image_label.hide()

        self.timer_text.setText(f"{msg.get('time_seconds', 10)}s")
        self.answers_label.setText("Answers: 0/?")
        self._current_time_seconds = msg.get("time_seconds", 10)

    def on_points_update(self, msg: dict):
        remaining_ms = msg.get("time_remaining_ms", 0)
        total_ms = self._current_time_seconds * 1000 if hasattr(self, '_current_time_seconds') else 10000
        pct = max(0, int((remaining_ms / total_ms) * 1000)) if total_ms > 0 else 0

        self.timer_bar.setValue(pct)
        self.points_label.setText(f"{msg.get('current_points', 0)} points")

        secs = max(0, remaining_ms / 1000)
        self.timer_text.setText(f"{secs:.0f}s")

    def on_choice_eliminated(self, msg: dict):
        pass

    def on_answer_count(self, msg: dict):
        self.answers_label.setText(f"Answers: {msg.get('answered', 0)}/{msg.get('total', 0)}")

    def on_question_end(self, msg: dict):
        correct = msg.get("correct_choice", "")
        self.timer_bar.hide()
        self.timer_text.setText("")
        self.points_label.setText("")
        self.image_label.hide()

        # Show the correct answer prominently
        self.correct_label.setText(f"Correct Answer:  {correct}")
        self.correct_label.show()

        self.answers_label.setText(
            f"Answers: {msg.get('answers_received', 0)}/{msg.get('total_players', 0)}"
        )

        # Show leaderboard
        scores = msg.get("player_scores", [])
        self.lb_title.setText("Leaderboard")
        self.lb_title.show()
        self._show_leaderboard(scores[:8])

    def on_game_end(self, msg: dict):
        self.timer_bar.hide()
        self.image_label.hide()
        self.correct_label.hide()

        self.question_label.setText("GAME OVER!")
        self.question_label.setFont(QFont("Segoe UI", 52, QFont.Weight.Bold))
        self.question_label.setStyleSheet("color: #fbbf24; padding: 20px;")
        self.progress_label.setText("")
        self.points_label.setText("")
        self.timer_text.setText("")
        self.answers_label.setText("")

        rankings = msg.get("final_rankings", [])
        self.lb_title.setText("Final Rankings")
        self.lb_title.show()
        self._show_leaderboard(rankings[:10])

    def _show_leaderboard(self, scores: list[dict]):
        # Clear old entries
        while self.lb_layout.count():
            item = self.lb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        top = scores[:3]
        # Podium arrangement: 2nd (left), 1st (center, tallest), 3rd (right)
        order = []
        if len(top) >= 2:
            order.append((2, top[1]))
        if len(top) >= 1:
            order.append((1, top[0]))
        if len(top) >= 3:
            order.append((3, top[2]))

        podium = QHBoxLayout()
        podium.setSpacing(24)
        podium.setContentsMargins(40, 12, 40, 12)
        podium.addStretch()

        heights = {1: 200, 2: 150, 3: 110}
        colors = {1: "#fbbf24", 2: "#9ca3af", 3: "#d97706"}
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}

        for place, s in order:
            col = QVBoxLayout()
            col.setSpacing(6)
            col.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)

            medal_lbl = QLabel(medals[place])
            medal_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            medal_lbl.setStyleSheet("font-size: 54px; background: transparent;")

            name_lbl = QLabel(s.get("name", ""))
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
            name_lbl.setStyleSheet(f"color: {colors[place]}; background: transparent;")

            score_lbl = QLabel(f"{s.get('total_score', 0):,} pts")
            score_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            score_lbl.setFont(QFont("Segoe UI", 16))
            score_lbl.setStyleSheet("color: #e2e8f0; background: transparent;")

            block = QFrame()
            block.setFixedHeight(heights[place])
            block.setMinimumWidth(180)
            block.setStyleSheet(
                f"background-color: {colors[place]}; border-top-left-radius: 12px; "
                f"border-top-right-radius: 12px;"
            )
            block_layout = QVBoxLayout(block)
            block_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            place_lbl = QLabel(str(place))
            place_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            place_lbl.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
            place_lbl.setStyleSheet("color: #0f172a; background: transparent;")
            block_layout.addWidget(place_lbl)

            col.addWidget(medal_lbl)
            col.addWidget(name_lbl)
            col.addWidget(score_lbl)
            col.addWidget(block)

            podium.addLayout(col)

        podium.addStretch()
        self.lb_layout.addLayout(podium)
        self.leaderboard_widget.show()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
