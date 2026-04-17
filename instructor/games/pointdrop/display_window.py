from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QProgressBar, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QKeyEvent


class ChoiceLabel(QFrame):
    """A styled label representing one answer choice."""

    def __init__(self, text: str = "", color: str = "#dc2626"):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(70)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 12px;
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.label.setStyleSheet("color: white;")
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self._eliminated = False
        self._base_color = color

    def set_text(self, text: str):
        self.label.setText(text)

    def set_eliminated(self, eliminated: bool):
        self._eliminated = eliminated
        if eliminated:
            self.setStyleSheet("""
                QFrame {
                    background-color: #374151;
                    border-radius: 12px;
                    padding: 12px;
                    opacity: 0.3;
                }
            """)
            self.label.setStyleSheet("color: #6b7280; text-decoration: line-through;")
            self.label.setText("ELIMINATED")
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {self._base_color};
                    border-radius: 12px;
                    padding: 12px;
                }}
            """)
            self.label.setStyleSheet("color: white;")

    def set_correct(self):
        self.setStyleSheet("""
            QFrame {
                background-color: #059669;
                border: 3px solid #10b981;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        self.label.setStyleSheet("color: white;")


class DisplayWindow(QWidget):
    """Fullscreen projector display for PointDrop games."""

    CHOICE_COLORS = ["#dc2626", "#2563eb", "#d97706", "#059669"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cognit - Display")
        self.setMinimumSize(1024, 700)
        self.setStyleSheet("background-color: #0f172a; color: white;")

        self._build_ui()
        self._show_waiting()

    def keyPressEvent(self, event: QKeyEvent):
        """Toggle fullscreen with F11 or Escape to exit fullscreen."""
        if event.key() == Qt.Key.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        elif event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 20)
        self.main_layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        self.progress_label = QLabel("")
        self.progress_label.setFont(QFont("Segoe UI", 16))
        self.progress_label.setStyleSheet("color: #94a3b8;")

        self.points_label = QLabel("")
        self.points_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.points_label.setStyleSheet("color: #34d399;")
        self.points_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        header.addWidget(self.progress_label)
        header.addStretch()
        header.addWidget(self.points_label)
        self.main_layout.addLayout(header)

        # Timer bar
        self.timer_bar = QProgressBar()
        self.timer_bar.setMaximum(1000)
        self.timer_bar.setValue(1000)
        self.timer_bar.setTextVisible(False)
        self.timer_bar.setMaximumHeight(12)
        self.timer_bar.setStyleSheet("""
            QProgressBar {
                background-color: #334155;
                border-radius: 6px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366f1, stop:1 #10b981);
                border-radius: 6px;
            }
        """)
        self.main_layout.addWidget(self.timer_bar)

        # Question text
        self.question_label = QLabel("")
        self.question_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("color: #e2e8f0; padding: 20px;")
        self.main_layout.addWidget(self.question_label)

        # Choices grid
        self.choices_grid = QGridLayout()
        self.choices_grid.setSpacing(16)
        self.choice_widgets: list[ChoiceLabel] = []
        for i in range(4):
            cw = ChoiceLabel("", self.CHOICE_COLORS[i])
            self.choice_widgets.append(cw)
            self.choices_grid.addWidget(cw, i // 2, i % 2)
        self.main_layout.addLayout(self.choices_grid)

        # Footer info
        footer = QHBoxLayout()
        self.answers_label = QLabel("")
        self.answers_label.setFont(QFont("Segoe UI", 14))
        self.answers_label.setStyleSheet("color: #94a3b8;")
        self.timer_text = QLabel("")
        self.timer_text.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.timer_text.setStyleSheet("color: #fbbf24;")
        self.timer_text.setAlignment(Qt.AlignmentFlag.AlignRight)
        footer.addWidget(self.answers_label)
        footer.addStretch()
        footer.addWidget(self.timer_text)
        self.main_layout.addLayout(footer)

        # Center message (for waiting/results)
        self.center_message = QLabel("")
        self.center_message.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        self.center_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_message.setStyleSheet("color: #818cf8;")
        self.center_message.hide()
        self.main_layout.addWidget(self.center_message)

        # Leaderboard area
        self.leaderboard_widget = QWidget()
        self.lb_layout = QVBoxLayout(self.leaderboard_widget)
        self.leaderboard_widget.hide()
        self.main_layout.addWidget(self.leaderboard_widget)

    def _show_waiting(self):
        self.question_label.setText("COGNIT")
        self.question_label.setStyleSheet("color: #818cf8; font-size: 48px; padding: 20px;")
        self.progress_label.setText("")
        self.points_label.setText("")
        self.timer_bar.hide()
        self.timer_text.setText("")
        self.answers_label.setText("Waiting for players...")
        for cw in self.choice_widgets:
            cw.hide()

    def _show_choices(self):
        for cw in self.choice_widgets:
            cw.show()

    # ── Event handlers called by the control panel ─────────────────────────

    def on_player_joined(self, msg: dict):
        self.answers_label.setText(f"{msg.get('player_count', 0)} players joined")

    def on_game_start(self, msg: dict):
        self.question_label.setText("Get Ready!")
        self.question_label.setStyleSheet("color: #e2e8f0; font-size: 36px; padding: 20px;")

    def on_question_start(self, msg: dict):
        self.timer_bar.show()
        self.timer_bar.setValue(1000)
        self._show_choices()
        self.leaderboard_widget.hide()
        self.center_message.hide()

        idx = msg.get("index", 0)
        total = msg.get("total", 0)
        self.progress_label.setText(f"Question {idx + 1} of {total}")
        self.points_label.setText(f"{msg.get('max_points', 1000)} points")

        self.question_label.setText(msg.get("text") or "")
        self.question_label.setStyleSheet("color: #e2e8f0; font-size: 24px; padding: 20px;")

        choices = msg.get("choices", [])
        for i, cw in enumerate(self.choice_widgets):
            if i < len(choices):
                cw.set_text(choices[i])
                cw.set_eliminated(False)
                cw.show()
            else:
                cw.hide()

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
        choice = msg.get("choice", "")
        for cw in self.choice_widgets:
            if cw.label.text() == choice:
                cw.set_eliminated(True)

    def on_answer_count(self, msg: dict):
        self.answers_label.setText(f"Answers: {msg.get('answered', 0)}/{msg.get('total', 0)}")

    def on_question_end(self, msg: dict):
        correct = msg.get("correct_choice", "")
        self.timer_bar.hide()
        self.timer_text.setText("")
        self.points_label.setText("")

        for cw in self.choice_widgets:
            if cw.label.text() == correct or (cw._eliminated and False):
                pass
            if not cw._eliminated:
                if cw.label.text() == correct:
                    cw.set_correct()

        self.answers_label.setText(
            f"Answers: {msg.get('answers_received', 0)}/{msg.get('total_players', 0)}"
        )

        # Show mini leaderboard
        scores = msg.get("player_scores", [])
        self._show_leaderboard(scores[:5])

    def on_game_end(self, msg: dict):
        self.timer_bar.hide()
        for cw in self.choice_widgets:
            cw.hide()

        self.question_label.setText("GAME OVER!")
        self.question_label.setStyleSheet("color: #fbbf24; font-size: 48px; padding: 20px;")
        self.progress_label.setText("")
        self.points_label.setText("")
        self.timer_text.setText("")
        self.answers_label.setText("")

        rankings = msg.get("final_rankings", [])
        self._show_leaderboard(rankings[:10])

    def _show_leaderboard(self, scores: list[dict]):
        # Clear old
        while self.lb_layout.count():
            item = self.lb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        medals = ["🥇", "🥈", "🥉"]
        for i, s in enumerate(scores):
            row = QLabel()
            medal = medals[i] if i < 3 else f"  {i + 1}."
            name = s.get("name", "")
            score = s.get("total_score", 0)
            row.setText(f"  {medal}  {name}    —    {score:,} pts")
            row.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold if i < 3 else QFont.Weight.Normal))
            color = "#fbbf24" if i == 0 else "#9ca3af" if i == 1 else "#d97706" if i == 2 else "#94a3b8"
            row.setStyleSheet(f"color: {color}; padding: 4px;")
            self.lb_layout.addWidget(row)

        self.leaderboard_widget.show()
