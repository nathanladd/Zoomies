from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QSizePolicy, QSplitter,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPalette, QKeyEvent, QPixmap, QMouseEvent

from version import __version__


class ProjectionWindow(QWidget):
    """Fullscreen projection display for Zoomies games.

    Shows question text, optional image, timer, answer count, and leaderboard.
    Answer choices are NOT shown here — students see them on their own devices.
    """

    _image_loaded = pyqtSignal(str, object)  # (image_url key, raw bytes or None)

    def __init__(self, game_id: int | None = None, join_code: str | None = None, server_host: str = "localhost", server_port: int = 5000):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.game_id = game_id
        self.join_code = join_code
        self.server_host = server_host
        self.server_port = server_port
        self.setWindowTitle(f"Zoomies v{__version__} — Projection")
        self.setMinimumSize(1024, 700)
        self.setStyleSheet("background-color: #FFFFFF; color: #333333;")

        self._is_waiting = False
        self._join_url = ""
        self._player_count = 0
        self._player_names: list[str] = []
        self._drag_pos = None
        self._current_image_url: str | None = None
        self._image_loaded.connect(self._on_image_loaded)
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
            "color: #AAAAAA; background: transparent; font-size: 11px;"
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
            "color: #AAAAAA; background: transparent; font-size: 11px;"
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
        self.progress_label.setStyleSheet("color: #555555;")

        self.points_label = QLabel("")
        self.points_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.points_label.setStyleSheet("color: #0078D4;")
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
                background-color: #E0E0E0;
                border-radius: 7px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0078D4, stop:1 #00A4C8);
                border-radius: 7px;
            }
        """)
        self.main_layout.addWidget(self.timer_bar)

        # ── Question text (large, centered) ────────────────────────────────
        self.question_label = QLabel("")
        self.question_label.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("color: #222222; padding: 24px;")
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
        self.answers_label.setStyleSheet("color: #555555;")
        self.answers_label.setTextFormat(Qt.TextFormat.RichText)
        self.answers_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_text = QLabel("")
        self.timer_text.setFont(QFont("Segoe UI", 36, QFont.Weight.Bold))
        self.timer_text.setStyleSheet("color: #0078D4;")
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
            "color: #2E7D32; background-color: #C8E6C9; border-radius: 12px; padding: 16px;"
        )
        self.correct_label.hide()
        self.main_layout.addWidget(self.correct_label)

        # ── Discussion & references reveal ─────────────────────────────────
        # Shown on the projector at question end (alongside the correct answer
        # reveal) so the class can see the discussion prompt and sources. The
        # note content is pushed in by the control panel, which fetches it at
        # question start. Hidden entirely when the question has no note.
        self.notes_frame = QFrame()
        self.notes_frame.setStyleSheet(
            "background-color: #F5F9FF; border: 1px solid #D0E4F5; border-radius: 12px;"
        )
        notes_layout = QVBoxLayout(self.notes_frame)
        notes_layout.setContentsMargins(28, 18, 28, 18)
        notes_layout.setSpacing(10)

        self.notes_discussion_label = QLabel("")
        self.notes_discussion_label.setFont(QFont("Segoe UI", 20))
        self.notes_discussion_label.setWordWrap(True)
        self.notes_discussion_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.notes_discussion_label.setStyleSheet("color: #222222; background: transparent;")
        notes_layout.addWidget(self.notes_discussion_label)

        self.notes_citations_label = QLabel("")
        self.notes_citations_label.setFont(QFont("Segoe UI", 14))
        self.notes_citations_label.setWordWrap(True)
        self.notes_citations_label.setOpenExternalLinks(True)
        self.notes_citations_label.setStyleSheet("color: #555555; background: transparent;")
        notes_layout.addWidget(self.notes_citations_label)

        self.notes_frame.hide()
        self.main_layout.addWidget(self.notes_frame)

        # ── Leaderboard area ──────────────────────────────────────────────
        self.lb_title = QLabel("")
        self.lb_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lb_title.setStyleSheet("color: #0078D4; padding-top: 8px;")
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
        self.hide_notes()
        self.lb_title.hide()
        self.leaderboard_widget.hide()

        self._join_url = f"{self.server_host}:{self.server_port}"

        self.question_label.setTextFormat(Qt.TextFormat.RichText)
        self.question_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._update_waiting_display()

    def _update_waiting_display(self):
        game_text = f"Game Code:&nbsp;&nbsp;<b>{self.join_code}</b>" if self.join_code else ""
        if self._player_count > 0:
            players_text = f'{self._player_count} player{"s" if self._player_count != 1 else ""} joined'
        else:
            players_text = "Waiting for players..."
        # Build player name list
        names_html = ""
        if self._player_names:
            name_spans = "&nbsp;&nbsp;&bull;&nbsp;&nbsp;".join(
                f'<span style="color:#333333;">{n}</span>' for n in self._player_names
            )
            names_html = (
                f'<div style="font-size:20px; color:#555555; margin-top:16px; '
                f'line-height:1.6;">{name_spans}</div>'
            )
        self.question_label.setText(
            f'<div style="text-align:center;">'
            f'<div style="font-size:64px; font-weight:bold; color:#0078D4; margin-bottom:12px; letter-spacing:2px;">Zoomies</div>'
            f'<div style="font-size:15px; color:#777777; margin-bottom:24px;">A classroom quiz game.</div>'
            f'<div style="font-size:20px; color:#555555; margin-bottom:4px;">Join at</div>'
            f'<div style="font-size:40px; font-weight:bold; color:#0078D4; margin-bottom:16px;">{self._join_url}</div>'
            f'<div style="font-size:32px; font-weight:bold; color:#2E7D32; margin-bottom:16px;">{game_text}</div>'
            f'<div style="font-size:22px; color:#555555;">{players_text}</div>'
            f'{names_html}'
            f'</div>'
        )

    def reset_for_new_game(self, game_id: int | None, join_code: str | None = None) -> None:
        """Refresh this projection window to advertise a new game.

        Called when the instructor starts a new game while this window is
        already open — we don't want to destroy/recreate the window (that
        loses fullscreen state and flashes a new window on the projector),
        we just snap back to the waiting screen with the new game code.
        """
        self.game_id = game_id
        self.join_code = join_code
        self.question_label.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        self.question_label.setStyleSheet("color: #222222; padding: 24px;")
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
        self.question_label.setStyleSheet("color: #222222; padding: 20px;")
        self.hide_notes()

    def on_question_start(self, msg: dict):
        self.timer_bar.show()
        self.timer_bar.setValue(1000)
        self.leaderboard_widget.hide()
        self.lb_title.hide()
        self.correct_label.hide()
        self.hide_notes()

        idx = msg.get("index", 0)
        total = msg.get("total", 0)
        self.progress_label.setText(f"Question {idx + 1} of {total}")
        self.points_label.setText(f"{msg.get('max_points', 1000)} points")

        self.question_label.setText(msg.get("text") or "")
        self.question_label.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        self.question_label.setStyleSheet("color: #222222; padding: 24px;")

        # Fetch image on a background thread so the GUI never blocks waiting
        # for the HTTP response. _on_image_loaded is called on the GUI thread
        # via the signal once the bytes arrive (or fail).
        image_url = msg.get("image_url")
        self._current_image_url = image_url
        self.image_label.hide()
        if image_url:
            self._fetch_image_async(image_url)

        self.timer_text.setText(f"{msg.get('time_seconds', 10)}s")
        self.answers_label.setText("Answers: 0/?")
        self._current_time_seconds = msg.get("time_seconds", 10)

    def _fetch_image_async(self, image_url: str) -> None:
        import threading
        http_scheme = "https" if self.server_port == 443 else "http"
        full_url = f"{http_scheme}://{self.server_host}:{self.server_port}/{image_url.lstrip('/')}"

        def _worker():
            try:
                import httpx
                resp = httpx.get(full_url, timeout=5.0)
                data = resp.content if resp.status_code == 200 else None
            except Exception:
                data = None
            self._image_loaded.emit(image_url, data)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_image_loaded(self, image_url: str, data: object) -> None:
        if self._current_image_url != image_url:
            return  # stale result from a previous question
        if not data:
            self.image_label.hide()
            return
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            self.image_label.hide()
            return
        max_h = min(350, max(100, self.height() // 3))
        if pixmap.height() > max_h:
            pixmap = pixmap.scaledToHeight(max_h, Qt.TransformationMode.SmoothTransformation)
        self.image_label.setPixmap(pixmap)
        self.image_label.show()

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

    def show_notes(self, note: dict | None) -> None:
        """Display the question's discussion prompt and references.

        Called by the control panel at question end, right after the correct
        answer is revealed. ``note`` is the dict returned by the notes API
        (``discussion`` / ``citations`` keys); ``None`` or an empty note hides
        the panel so questions without a note leave no empty box on screen.
        """
        note = note or {}
        discussion = (note.get("discussion") or "").strip()
        citations = (note.get("citations") or "").strip()
        if discussion:
            self.notes_discussion_label.setText(discussion)
            self.notes_discussion_label.show()
        else:
            self.notes_discussion_label.hide()
        if citations:
            self.notes_citations_label.setText(f"References:  {citations}")
            self.notes_citations_label.show()
        else:
            self.notes_citations_label.hide()
        self.notes_frame.setVisible(bool(discussion or citations))

    def hide_notes(self) -> None:
        self.notes_frame.hide()

    def on_game_end(self, msg: dict):
        self.timer_bar.hide()
        self.image_label.hide()
        self.correct_label.hide()
        self.hide_notes()

        self.question_label.setText("GAME OVER!")
        self.question_label.setFont(QFont("Segoe UI", 52, QFont.Weight.Bold))
        self.question_label.setStyleSheet("color: #0078D4; padding: 20px;")
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
            score_lbl.setStyleSheet("color: #333333; background: transparent;")

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
            place_lbl.setStyleSheet("color: #333333; background: transparent;")
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
