import json
import os
import subprocess
import sys
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QSplitter,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QProcess, QObject
from PyQt6.QtGui import QTextCursor

from instructor.api_client import ApiClient
from instructor.game.projection_window import ProjectionWindow


def kill_port_processes(port: int = 5000):
    """Kill any process currently listening on the given port (Windows)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        pids = set()
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    try:
                        pids.add(int(parts[-1]))
                    except ValueError:
                        pass
        my_pid = os.getpid()
        for pid in pids:
            if pid == my_pid or pid == 0:
                continue
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
                )
                print(f"[SERVER] Killed stale process on port {port} (PID {pid})")
            except Exception:
                pass
    except Exception:
        pass


class LogStream(QObject):
    """Redirect writes to a Qt signal so they appear in a QPlainTextEdit."""
    text_written = pyqtSignal(str)

    def __init__(self, original_stream=None):
        super().__init__()
        self._original = original_stream

    def write(self, text: str):
        if text.strip():
            self.text_written.emit(text)
        if self._original:
            self._original.write(text)

    def flush(self):
        if self._original:
            self._original.flush()

try:
    import websockets
    import asyncio
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class WebSocketThread(QThread):
    """Background thread to manage the instructor WebSocket connection."""
    message_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, game_id: int, host: str = "localhost", port: int = 5000):
        super().__init__()
        self.game_id = game_id
        self.host = host
        self.port = port
        self._running = False
        self._ws = None
        self._loop = None
        self._send_queue: list[str] = []

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())

    async def _connect(self):
        uri = f"ws://{self.host}:{self.port}/ws/instructor/{self.game_id}"
        print(f"[INSTR-WS] Connecting to {uri}")
        try:
            async with websockets.connect(uri) as ws:
                self._ws = ws
                self._running = True
                print(f"[INSTR-WS] Connected!")
                self.connected.emit()

                while self._running:
                    # Send any queued messages
                    while self._send_queue:
                        msg = self._send_queue.pop(0)
                        print(f"[INSTR-WS] Sending: {msg}")
                        await ws.send(msg)

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.1)
                        data = json.loads(raw)
                        msg_type = data.get('type', '?')
                        # points_update is high-frequency; the GUI thread renders
                        # it as a single self-overwriting spinner line instead.
                        if msg_type != 'points_update':
                            print(f"[INSTR-WS] Received: {msg_type}")
                        self.message_received.emit(data)
                    except asyncio.TimeoutError:
                        continue
                    except websockets.ConnectionClosed as e:
                        print(f"[INSTR-WS] Connection closed (code={e.code})")
                        break
                    except Exception as e:
                        print(f"[INSTR-WS] recv error: {e}")
                        break

        except Exception as e:
            print(f"[INSTR-WS] Connection failed: {e}")
        finally:
            self._running = False
            self.disconnected.emit()

    def send(self, data: dict):
        self._send_queue.append(json.dumps(data))

    def stop(self):
        self._running = False


class GameControlPanel(QWidget):
    # Emitted whenever the projection window's visibility changes so the
    # View menu checkmark can stay in sync.
    projection_visibility_changed = pyqtSignal(bool)
    # Emitted when the user clicks "Restart Server" — MainWindow handles the
    # actual stop/start since it owns the QProcess.
    restart_server_requested = pyqtSignal()

    def __init__(self, api: ApiClient, server_process: QProcess | None = None):
        super().__init__()
        self.api = api
        self.ws_thread: WebSocketThread | None = None
        self.projection_window: ProjectionWindow | None = None
        self.current_game_id: int | None = None
        self._players: dict[int, str] = {}  # player_id -> name
        # player_id -> bool (True correct, False wrong) for the current question.
        # Cleared on every new question_start and on game_end.
        self._answer_status: dict[int, bool] = {}
        self._server_process = server_process  # owned by MainWindow
        # Spinner state for collapsing points_update log lines
        self._points_spinner_idx = 0
        self._points_line_active = False
        self._build_ui()
        self._setup_log_redirect()
        if self._server_process is not None:
            self._server_process.readyReadStandardOutput.connect(self._read_server_output)
            self._server_process.finished.connect(self._on_server_finished)
            self.server_console.appendPlainText("--- Server running ---")
        self._refresh_quizzes()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ── Setup Group ────────────────────────────────────────────────────
        setup_group = QGroupBox("Game Setup")
        setup_layout = QVBoxLayout(setup_group)

        row1 = QHBoxLayout()
        self.quiz_combo = QComboBox()
        self.quiz_combo.setMinimumWidth(250)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_quizzes)
        self.btn_create_game = QPushButton("New Game")
        self.btn_create_game.clicked.connect(self._create_game)
        self.btn_create_game.setStyleSheet(
            "QPushButton { background-color: #86efac; color: #052e16; "
            "font-weight: bold; padding: 4px 12px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #4ade80; } "
            "QPushButton:pressed { background-color: #22c55e; }"
        )
        row1.addWidget(QLabel("Quiz:"))
        row1.addWidget(self.quiz_combo)
        row1.addWidget(btn_refresh)
        row1.addWidget(self.btn_create_game)
        row1.addStretch()
        setup_layout.addLayout(row1)

        layout.addWidget(setup_group)

        # ── Controls Group ─────────────────────────────────────────────────
        controls_group = QGroupBox("Game Controls")
        controls_layout = QVBoxLayout(controls_group)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-size: 14px;")
        self.game_label = QLabel("No active game")
        self.game_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(self.game_label)
        controls_layout.addLayout(status_row)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Game")
        self.btn_start.clicked.connect(self._start_game)
        self.btn_start.setEnabled(False)
        self.btn_next = QPushButton("First Question")
        self.btn_next.clicked.connect(self._next_question)
        self.btn_next.setEnabled(False)
        self.btn_reveal = QPushButton("Reveal Answer")
        self.btn_reveal.clicked.connect(self._reveal)
        self.btn_reveal.setEnabled(False)
        self.btn_end = QPushButton("End Game")
        self.btn_end.clicked.connect(self._end_game)
        self.btn_end.setEnabled(False)

        for btn in [self.btn_start, self.btn_next, self.btn_reveal, self.btn_end]:
            btn.setMinimumHeight(40)
            btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        # Applied after the shared style so it isn't overwritten.
        self.btn_end.setStyleSheet(
            "QPushButton { font-size: 14px; font-weight: bold; "
            "background-color: #fca5a5; color: #450a0a; } "
            "QPushButton:hover { background-color: #f87171; } "
            "QPushButton:pressed { background-color: #ef4444; } "
            "QPushButton:disabled { background-color: #4b1d1d; color: #9a6a6a; }"
        )
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_next)
        btn_row.addWidget(self.btn_reveal)
        btn_row.addWidget(self.btn_end)
        controls_layout.addLayout(btn_row)

        # Info row
        info_row = QHBoxLayout()
        self.q_label = QLabel("Question: -")
        self.players_label = QLabel("Players: 0")
        self.answers_label = QLabel("Answers: 0/0")
        self.time_label = QLabel("Time: -")
        for lbl in [self.q_label, self.players_label, self.answers_label, self.time_label]:
            lbl.setStyleSheet("font-size: 13px;")
            info_row.addWidget(lbl)
        controls_layout.addLayout(info_row)

        layout.addWidget(controls_group)

        # ── Current Question ──────────────────────────────────────────────
        qa_group = QGroupBox("Current Question")
        qa_layout = QVBoxLayout(qa_group)
        self.qa_question_label = QLabel("")
        self.qa_question_label.setWordWrap(True)
        self.qa_question_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        qa_layout.addWidget(self.qa_question_label)
        self.qa_choices_layout = QVBoxLayout()
        qa_layout.addLayout(self.qa_choices_layout)
        self._qa_choice_labels: list[QLabel] = []
        layout.addWidget(qa_group)

        # ── Dockable panels (built here, docked by MainWindow) ────────────
        # The leaderboard and both consoles live in QDockWidgets owned by
        # MainWindow so the instructor can move/hide them. The dock widget's
        # title bar already labels each panel, so the inner container is a
        # plain QWidget with no additional title.
        self.leaderboard_group = QWidget()
        lb_layout = QVBoxLayout(self.leaderboard_group)
        lb_layout.setContentsMargins(0, 0, 0, 0)
        self.lb_table = QTableWidget()
        self.lb_table.setColumnCount(4)
        self.lb_table.setHorizontalHeaderLabels(["Rank", "Name", "Answer", "Score"])
        self.lb_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.lb_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lb_layout.addWidget(self.lb_table)

        self.server_console_group = QWidget()
        srv_layout = QVBoxLayout(self.server_console_group)
        srv_layout.setContentsMargins(0, 0, 0, 0)
        srv_toolbar = QHBoxLayout()
        srv_toolbar.setContentsMargins(0, 0, 0, 0)
        self.restart_server_btn = QPushButton("Restart Server")
        self.restart_server_btn.setToolTip(
            "Kill and relaunch the backend server on port 5000. "
            "Use this if API calls start returning errors mid-game."
        )
        self.restart_server_btn.clicked.connect(self._on_restart_server_clicked)
        srv_toolbar.addWidget(self.restart_server_btn)
        srv_toolbar.addStretch()
        self.server_version_label = QLabel("Server: …")
        self.server_version_label.setStyleSheet("color: #94a3b8; padding: 0 6px;")
        self.server_version_label.setToolTip("Version reported by GET /api/version")
        srv_toolbar.addWidget(self.server_version_label)
        srv_layout.addLayout(srv_toolbar)
        # Version label is refreshed only at startup and after a server
        # restart (see set_server_process); no periodic polling.
        QTimer.singleShot(800, self._refresh_server_version)
        self.server_console = QPlainTextEdit()
        self.server_console.setReadOnly(True)
        self.server_console.setMaximumBlockCount(500)
        self.server_console.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; "
            "background-color: #1a1a2e; color: #a5b4fc;"
        )
        srv_layout.addWidget(self.server_console)

        self.instructor_console_group = QWidget()
        instr_layout = QVBoxLayout(self.instructor_console_group)
        instr_layout.setContentsMargins(0, 0, 0, 0)
        self.instructor_console = QPlainTextEdit()
        self.instructor_console.setReadOnly(True)
        self.instructor_console.setMaximumBlockCount(500)
        self.instructor_console.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; "
            "background-color: #1a1a2e; color: #6ee7b7;"
        )
        instr_layout.addWidget(self.instructor_console)

        layout.addStretch(1)

    def _refresh_quizzes(self):
        self.quiz_combo.clear()
        try:
            quizzes = self.api.list_quizzes()
            for qz in quizzes:
                self.quiz_combo.addItem(f"{qz['name']} ({qz.get('question_count', 0)} Q's)", qz["id"])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load quizzes: {e}")

    def _create_game(self):
        quiz_id = self.quiz_combo.currentData()
        if quiz_id is None:
            QMessageBox.warning(self, "Error", "Select a quiz first.")
            return

        # End any in-progress game before spinning up the new one. This keeps
        # the server-side engine/DB state tidy and frees the WS slot.
        self._stop_current_game()
        self._reset_ui_for_new_game()

        try:
            game = self.api.create_game(quiz_id)
            self.current_game_id = game["id"]
            self.api.init_game(self.current_game_id)
            self.game_label.setText(f"Game #{self.current_game_id} (waiting)")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create game: {e}")
            return

        # Make sure the projector is showing the new game number. The window
        # is a persistent singleton — we reuse it (keeping fullscreen /
        # position) if it exists, lazily create it otherwise, and always
        # ensure it's visible at the start of a new game.
        if self.projection_window is None:
            self.projection_window = ProjectionWindow(
                game_id=self.current_game_id,
                server_port=5000,
            )
        else:
            self.projection_window.reset_for_new_game(self.current_game_id)
        self.projection_window.show()
        self.projection_visibility_changed.emit(True)

        self._connect_ws()

    def _stop_current_game(self) -> None:
        """Cleanly terminate whatever game is currently running (if any)."""
        # Disconnect the existing WS thread first so its disconnected signal
        # doesn't race with the new game's connected signal.
        if self.ws_thread is not None:
            try:
                if self.ws_thread.isRunning():
                    # Ask the server to finish cleanly; the handler updates DB
                    # status and evicts the engine from active_games.
                    self.ws_thread.send({"type": "end_game"})
                self.ws_thread.stop()
                self.ws_thread.wait(1000)
            except Exception:
                pass
            self.ws_thread = None

        # REST fallback: even if the WS never flushed end_game, the DB row for
        # the old game should be marked finished. Ignored if already finished.
        if self.current_game_id is not None:
            try:
                self.api.end_game(self.current_game_id)
            except Exception:
                pass

    def _reset_ui_for_new_game(self) -> None:
        """Clear labels, leaderboard, question area, and button states."""
        self._players.clear()
        self._answer_status.clear()
        self.lb_table.setRowCount(0)
        self._clear_question()
        self.q_label.setText("Question: -")
        self.players_label.setText("Players: 0")
        self.answers_label.setText("Answers: 0/0")
        self.time_label.setText("Time: -")
        self.status_label.setText("Status: Connecting...")
        self.btn_start.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_next.setText("First Question")
        self.btn_reveal.setEnabled(False)
        self.btn_end.setEnabled(False)

    def _connect_ws(self):
        if not HAS_WEBSOCKETS:
            QMessageBox.warning(self, "Error", "websockets package not installed")
            return
        if self.current_game_id is None:
            return

        self.ws_thread = WebSocketThread(self.current_game_id)
        self.ws_thread.message_received.connect(self._on_ws_message)
        self.ws_thread.connected.connect(self._on_ws_connected)
        self.ws_thread.disconnected.connect(self._on_ws_disconnected)
        self.ws_thread.start()

    def _on_ws_connected(self):
        self.status_label.setText("Status: Connected (waiting for players)")
        self.btn_start.setEnabled(True)
        self.btn_end.setEnabled(True)

    def _on_ws_disconnected(self):
        self.status_label.setText("Status: Disconnected")
        self.btn_start.setEnabled(False)
        self.btn_next.setEnabled(False)
        self.btn_reveal.setEnabled(False)
        self.btn_end.setEnabled(False)

    def _on_ws_message(self, msg: dict):
        msg_type = msg.get("type")

        if msg_type == "player_joined":
            self.players_label.setText(f"Players: {msg.get('player_count', 0)}")
            pid = msg.get("player_id")
            name = msg.get("name", "")
            if pid is not None:
                self._players[pid] = name
            self._update_leaderboard_from_players()
            if self.projection_window:
                self.projection_window.on_player_joined(msg)

        elif msg_type == "player_left":
            self.players_label.setText(f"Players: {msg.get('player_count', 0)}")
            pid = msg.get("player_id")
            self._players.pop(pid, None)
            self._update_leaderboard_from_players()

        elif msg_type == "game_start":
            self.status_label.setText("Status: Game started!")
            if self.current_game_id is not None:
                self.game_label.setText(f"Game #{self.current_game_id} (running)")
            self.btn_start.setEnabled(False)
            self.btn_next.setEnabled(True)
            if self.projection_window:
                self.projection_window.on_game_start(msg)

        elif msg_type == "question_start":
            idx = msg.get("index", 0)
            total = msg.get("total", 0)
            self.q_label.setText(f"Question: {idx + 1} / {total}")
            self.answers_label.setText(f"Answers: 0/?")
            self.btn_next.setEnabled(False)
            self.btn_next.setText("Next Question")
            self.btn_reveal.setEnabled(True)
            # Reset per-question answer markers and refresh leaderboard so the
            # ✓/✗ column clears between questions.
            self._answer_status.clear()
            self._update_leaderboard_from_players()
            self._show_question(msg)
            if self.projection_window:
                self.projection_window.on_question_start(msg)

        elif msg_type == "question_answer":
            self._highlight_correct(msg.get("correct_answer", ""))

        elif msg_type == "points_update":
            remaining = msg.get("time_remaining_ms", 0)
            secs = remaining / 1000
            self.time_label.setText(f"Time: {secs:.1f}s | Pts: {msg.get('current_points', 0)}")
            self._log_points_tick()
            if self.projection_window:
                self.projection_window.on_points_update(msg)

        elif msg_type == "choice_eliminated":
            if self.projection_window:
                self.projection_window.on_choice_eliminated(msg)

        elif msg_type == "player_answered":
            pid = msg.get("player_id")
            if pid is not None:
                self._answer_status[pid] = bool(msg.get("is_correct", False))
                self._refresh_answer_column()

        elif msg_type == "answer_count":
            self.answers_label.setText(f"Answers: {msg.get('answered', 0)}/{msg.get('total', 0)}")
            if self.projection_window:
                self.projection_window.on_answer_count(msg)

        elif msg_type == "question_end":
            self.btn_reveal.setEnabled(False)
            self.btn_next.setEnabled(True)
            self.time_label.setText("Time: -")
            self._update_leaderboard(msg.get("player_scores", []))
            if self.projection_window:
                self.projection_window.on_question_end(msg)

        elif msg_type == "game_end":
            self.status_label.setText("Status: Game finished!")
            self.game_label.setText("No active game")
            self.current_game_id = None
            self.btn_next.setEnabled(False)
            self.btn_reveal.setEnabled(False)
            self.btn_end.setEnabled(False)
            self._players.clear()
            self._answer_status.clear()
            self.lb_table.setRowCount(0)
            self._clear_question()
            if self.projection_window:
                self.projection_window.on_game_end(msg)

    def _start_game(self):
        if self.ws_thread:
            self.ws_thread.send({"type": "start_game"})

    def _next_question(self):
        if self.ws_thread:
            self.ws_thread.send({"type": "next_question"})

    def _reveal(self):
        if self.ws_thread:
            self.ws_thread.send({"type": "reveal"})

    def _end_game(self):
        reply = QMessageBox.question(
            self, "Confirm", "End the game?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self.ws_thread:
            self.ws_thread.send({"type": "end_game"})

    def toggle_projection(self) -> bool:
        """Show/hide the projection window. Returns new visible state.

        The projection window is a long-lived singleton: all WS-driven
        updates keep flowing into it regardless of visibility, so toggling
        is just a show/hide. On first toggle it's lazily created.
        """
        if self.projection_window is None:
            self.projection_window = ProjectionWindow(
                game_id=self.current_game_id,
                server_port=5000,
            )

        if self.projection_window.isVisible():
            self.projection_window.hide()
            visible = False
        else:
            self.projection_window.show()
            visible = True
        self.projection_visibility_changed.emit(visible)
        return visible

    def is_projection_visible(self) -> bool:
        return self.projection_window is not None and self.projection_window.isVisible()

    def _update_leaderboard(self, scores: list[dict]):
        self.lb_table.setRowCount(len(scores))
        for row, s in enumerate(scores):
            rank = s.get("rank", row + 1)
            self.lb_table.setItem(row, 0, QTableWidgetItem(str(rank)))
            self.lb_table.setItem(row, 1, QTableWidgetItem(s.get("name", "")))
            score = s.get("total_score", 0)
            self.lb_table.setItem(row, 3, QTableWidgetItem(str(score)))
            # Reveal payload carries is_correct/selected per player; prefer
            # that over the running _answer_status so the marker stays
            # accurate even for players who never submitted.
            pid = s.get("player_id")
            if "is_correct" in s and s.get("selected") is not None:
                self._set_answer_cell(row, bool(s["is_correct"]))
            elif pid in self._answer_status:
                self._set_answer_cell(row, self._answer_status[pid])
            else:
                self._set_answer_cell(row, None)

    def _show_question(self, msg: dict):
        self.qa_question_label.setText(msg.get("text", ""))
        # Clear old choice labels
        for lbl in self._qa_choice_labels:
            self.qa_choices_layout.removeWidget(lbl)
            lbl.deleteLater()
        self._qa_choice_labels.clear()
        # Add new choice labels
        for choice in msg.get("choices", []):
            lbl = QLabel(f"  {choice}")
            lbl.setStyleSheet("font-size: 13px; padding: 2px 8px; border-radius: 4px;")
            self.qa_choices_layout.addWidget(lbl)
            self._qa_choice_labels.append(lbl)

    def _highlight_correct(self, correct: str):
        for lbl in self._qa_choice_labels:
            text = lbl.text().strip()
            if text == correct:
                lbl.setStyleSheet(
                    "font-size: 13px; padding: 2px 8px; border-radius: 4px; "
                    "background-color: #065f46; color: #34d399; font-weight: bold;"
                )

    def _clear_question(self):
        self.qa_question_label.setText("")
        for lbl in self._qa_choice_labels:
            self.qa_choices_layout.removeWidget(lbl)
            lbl.deleteLater()
        self._qa_choice_labels.clear()

    def _update_leaderboard_from_players(self):
        """Show all joined players with score 0, sorted by name."""
        items = sorted(self._players.items(), key=lambda kv: kv[1].lower())
        self.lb_table.setRowCount(len(items))
        for row, (pid, name) in enumerate(items):
            self.lb_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.lb_table.setItem(row, 1, QTableWidgetItem(name))
            self.lb_table.setItem(row, 3, QTableWidgetItem("0"))
            self._set_answer_cell(row, self._answer_status.get(pid))

    def _refresh_answer_column(self):
        """Update only the Answer column for the current rows by matching name.

        The leaderboard rows are keyed by player name (the same source used
        when building them), so we resolve each row back to a player_id via
        self._players to look up its current ✓/✗ state.
        """
        name_to_pid = {n: pid for pid, n in self._players.items()}
        for row in range(self.lb_table.rowCount()):
            name_item = self.lb_table.item(row, 1)
            if not name_item:
                continue
            pid = name_to_pid.get(name_item.text())
            self._set_answer_cell(row, self._answer_status.get(pid))

    def _set_answer_cell(self, row: int, is_correct: bool | None):
        """Set the Answer column cell for a row. None clears the marker."""
        if is_correct is None:
            item = QTableWidgetItem("")
        elif is_correct:
            item = QTableWidgetItem("\u2713")  # ✓
            item.setForeground(Qt.GlobalColor.green)
        else:
            item = QTableWidgetItem("\u2717")  # ✗
            item.setForeground(Qt.GlobalColor.red)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self.lb_table.setItem(row, 2, item)

    # ── Log redirect ──────────────────────────────────────────────────────

    def _setup_log_redirect(self):
        self._log_stream = LogStream(sys.stdout)
        self._log_stream.text_written.connect(self._append_instructor_log)
        sys.stdout = self._log_stream

    def _append_instructor_log(self, text: str):
        # Any unrelated log output breaks the points_update spinner line.
        self._points_line_active = False
        self.instructor_console.appendPlainText(text.rstrip())
        sb = self.instructor_console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _log_points_tick(self):
        """Render points_update as a single self-overwriting spinner line."""
        spinner = "|/-\\"[self._points_spinner_idx % 4]
        self._points_spinner_idx += 1
        text = f"[INSTR-WS] Received: points_update  {spinner}"
        cursor = self.instructor_console.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self._points_line_active:
            # Replace the contents of the current (last) block in place.
            cursor.movePosition(
                QTextCursor.MoveOperation.StartOfBlock,
                QTextCursor.MoveMode.KeepAnchor,
            )
            cursor.removeSelectedText()
            cursor.insertText(text)
            # Keep the view pinned to the bottom without jitter.
            sb = self.instructor_console.verticalScrollBar()
            sb.setValue(sb.maximum())
        else:
            self.instructor_console.appendPlainText(text)
            self._points_line_active = True

    # ── Server console (process is owned by MainWindow) ───────────────────────────

    def _read_server_output(self):
        if self._server_process:
            data = self._server_process.readAllStandardOutput()
            text = bytes(data).decode("utf-8", errors="replace")
            appended = False
            for line in text.splitlines():
                if line.strip():
                    self.server_console.appendPlainText(line)
                    appended = True
            if appended:
                sb = self.server_console.verticalScrollBar()
                sb.setValue(sb.maximum())

    def _on_server_finished(self, exit_code, exit_status):
        self.server_console.appendPlainText(f"--- Server exited (code {exit_code}) ---")

    def _on_restart_server_clicked(self):
        confirm = QMessageBox.question(
            self, "Restart Server",
            "Kill and relaunch the backend server?\n\n"
            "Any in-progress game state held only in server memory will be lost. "
            "Player scores and questions in the database are not affected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self.server_console.appendPlainText("--- Restart requested by user ---")
        self.restart_server_btn.setEnabled(False)
        QTimer.singleShot(2000, lambda: self.restart_server_btn.setEnabled(True))
        self.restart_server_requested.emit()

    def _refresh_server_version(self) -> None:
        """Poll /api/version and update the label. Runs every few seconds and
        immediately after a restart so the user can verify they're on the
        intended build."""
        try:
            import httpx
            r = httpx.get("http://127.0.0.1:5000/api/version", timeout=1.0)
            if r.status_code == 200:
                v = r.json().get("version", "?")
                self.server_version_label.setText(f"Server: v{v}")
                self.server_version_label.setStyleSheet("color: #34d399; padding: 0 6px;")
                return
        except Exception:
            pass
        self.server_version_label.setText("Server: offline")
        self.server_version_label.setStyleSheet("color: #f87171; padding: 0 6px;")

    def set_server_process(self, proc: QProcess | None) -> None:
        """Swap in a new server QProcess after MainWindow restarts it.

        Re-wires log piping and the exit-notification slot so the console
        keeps working across restarts.
        """
        self._server_process = proc
        if proc is not None:
            proc.readyReadStandardOutput.connect(self._read_server_output)
            proc.finished.connect(self._on_server_finished)
            self.server_console.appendPlainText("--- Server running ---")
        QTimer.singleShot(800, self._refresh_server_version)

    def closeEvent(self, event):
        # Restore stdout
        if hasattr(self, '_log_stream') and self._log_stream._original:
            sys.stdout = self._log_stream._original
        if self.ws_thread:
            self.ws_thread.stop()
            self.ws_thread.wait(2000)
        if self.projection_window:
            self.projection_window.close()
        event.accept()
