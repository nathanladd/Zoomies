import json
import threading
from collections import deque

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QSpinBox, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut

from instructor.api_client import ApiClient
from instructor.game.projection_window import ProjectionWindow


try:
    import websockets
    import asyncio
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class LogWebSocketThread(QThread):
    """Background thread that connects to the server's /ws/logs endpoint
    and emits each log line as a signal for the server console."""
    line_received = pyqtSignal(str)
    status_changed = pyqtSignal(str)  # connection status messages

    def __init__(self, host: str, port: int, token: str | None = None):
        super().__init__()
        self.host = host
        self.port = port
        self.token = token
        self._running = False

    def run(self):
        if not HAS_WEBSOCKETS:
            self.status_changed.emit("[Log] websockets package not installed")
            return
        self._running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._listen())
        loop.close()

    async def _listen(self):
        suffix = f"?token={self.token}" if self.token else ""
        ws_scheme = "wss" if self.port == 443 else "ws"
        url = f"{ws_scheme}://{self.host}:{self.port}/ws/logs{suffix}"
        self.status_changed.emit(f"[Log] Connecting to {url} ...")
        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    self.status_changed.emit("[Log] Connected — streaming server output")
                    while self._running:
                        try:
                            line = await asyncio.wait_for(ws.recv(), timeout=0.5)
                            self.line_received.emit(line)
                        except asyncio.TimeoutError:
                            continue
                    self.status_changed.emit("[Log] Disconnected")
            except Exception as exc:
                if not self._running:
                    break
                self.status_changed.emit(f"[Log] Connection failed: {exc} — retrying in 2s")
                await asyncio.sleep(2)

    def stop(self):
        self._running = False


class WebSocketThread(QThread):
    """Background thread to manage the instructor WebSocket connection."""
    message_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(self, game_id: int, host: str = "localhost", port: int = 5000, token: str | None = None):
        super().__init__()
        self.game_id = game_id
        self.host = host
        self.port = port
        self.token = token
        self._running = False
        self._ws = None
        self._loop = None
        self._send_queue: deque[str] = deque()

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect())

    async def _connect(self):
        suffix = f"?token={self.token}" if self.token else ""
        ws_scheme = "wss" if self.port == 443 else "ws"
        uri = f"{ws_scheme}://{self.host}:{self.port}/ws/instructor/{self.game_id}{suffix}"
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
                        msg = self._send_queue.popleft()
                        print(f"[INSTR-WS] Sending: {msg}")
                        await ws.send(msg)

                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.1)
                        data = json.loads(raw)
                        msg_type = data.get('type', '?')
                        # points_update is high-frequency; the GUI thread renders
                        # it as a single self-overwriting spinner line instead.
                        if msg_type == 'player_answered':
                            pname = data.get('name', '?')
                            print(f"[INSTR-WS] Received: {pname} answered")
                        elif msg_type != 'points_update':
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
    # Emitted from the background stats-fetch thread once the HTTP roundtrip
    # to /api/questions/{id}/stats finishes. Carries (question_id, stats_dict)
    # so the GUI slot can verify the result still matches the active question.
    _stats_loaded = pyqtSignal(int, dict)
    _version_loaded = pyqtSignal(str, str)  # (label_text, stylesheet)
    _image_loaded = pyqtSignal(str, object)  # (image_url key, raw bytes or None)
    _status_polled = pyqtSignal(int)  # active_games count

    def __init__(self, api: ApiClient, server_host: str = "localhost", server_port: int = 5000):
        super().__init__()
        self.api = api
        self.server_host = server_host
        self.server_port = server_port
        self.ws_thread: WebSocketThread | None = None
        self.projection_window: ProjectionWindow | None = None
        self.current_game_id: int | None = None
        self.current_join_code: str | None = None
        self._players: dict[int, str] = {}  # player_id -> name
        # player_id -> bool (True correct, False wrong) for the current question.
        # Cleared on every new question_start and on game_end.
        self._answer_status: dict[int, bool] = {}
        self._log_ws: LogWebSocketThread | None = None
        self._quiz_question_counts: dict[int, int] = {}
        self._quiz_randomize_defaults: dict[int, bool] = {}
        self._current_image_url: str | None = None
        self._build_ui()
        # Marshal background-thread stat results back onto the GUI thread.
        self._stats_loaded.connect(self._on_stats_loaded)
        self._version_loaded.connect(self._on_version_loaded)
        self._image_loaded.connect(self._on_image_loaded)
        self._status_polled.connect(self._on_status_polled)
        self._connect_log_ws()
        self._refresh_quizzes()
        QTimer.singleShot(1000, self._poll_active_games)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(10_000)
        self._poll_timer.timeout.connect(self._poll_active_games)
        self._poll_timer.start()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # ── Setup Group ────────────────────────────────────────────────────
        setup_group = QGroupBox("Game Setup")
        setup_layout = QVBoxLayout(setup_group)

        row1 = QHBoxLayout()
        self.quiz_combo = QComboBox()
        self.quiz_combo.setMinimumWidth(250)
        self.quiz_combo.currentIndexChanged.connect(self._on_quiz_selection_changed)
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self._refresh_quizzes)
        self.btn_create_game = QPushButton("New Game")
        self.btn_create_game.clicked.connect(self._create_game)
        self.btn_create_game.setStyleSheet(
            "QPushButton { background-color: #2E7D32; color: white; "
            "font-weight: bold; padding: 4px 12px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #1b5e20; } "
            "QPushButton:pressed { background-color: #1b5e20; }"
        )
        row1.addWidget(QLabel("Quiz:"))
        row1.addWidget(self.quiz_combo)
        row1.addWidget(btn_refresh)
        row1.addWidget(self.btn_create_game)
        row1.addStretch()
        setup_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.total_questions_label = QLabel("Total questions: —")
        self.total_questions_label.setStyleSheet("color: #888888; font-size: 12px;")
        self.question_count_spin = QSpinBox()
        self.question_count_spin.setMinimum(1)
        self.question_count_spin.setMaximum(1)
        self.question_count_spin.setValue(1)
        self.question_count_spin.setEnabled(False)
        self.question_count_spin.setToolTip("Number of questions to include (randomly selected)")
        self.randomize_order_check = QCheckBox("Randomize order")
        row2.addWidget(self.total_questions_label)
        row2.addSpacing(16)
        row2.addWidget(QLabel("Questions to use:"))
        row2.addWidget(self.question_count_spin)
        row2.addSpacing(16)
        row2.addWidget(self.randomize_order_check)
        row2.addStretch()
        setup_layout.addLayout(row2)

        layout.addWidget(setup_group)

        # ── Controls Group ─────────────────────────────────────────────────
        controls_group = QGroupBox("Game Controls")
        controls_layout = QVBoxLayout(controls_group)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-size: 14px;")
        self.game_label = QLabel("No active game")
        self.game_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.active_games_label = QLabel("Active games: —")
        self.active_games_label.setStyleSheet("font-size: 13px; color: #888888;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(self.active_games_label)
        status_row.addSpacing(16)
        status_row.addWidget(self.game_label)
        controls_layout.addLayout(status_row)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Game")
        self.btn_start.clicked.connect(self._start_game)
        self.btn_start.setEnabled(False)
        self.btn_next = QPushButton("First Question")
        self.btn_next.clicked.connect(self._next_question)
        self.btn_next.setEnabled(False)
        self.btn_next.setToolTip("Space")
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
            "background-color: #ffe6e6; color: #cc0000; border: 1px solid #ffcccc; } "
            "QPushButton:hover { background-color: #ffcccc; border-color: #ff9999; } "
            "QPushButton:pressed { background-color: #ffb3b3; } "
            "QPushButton:disabled { background-color: #f5f5f5; color: #aaaaaa; }"
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
        self.qa_image_label = QLabel()
        self.qa_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qa_image_label.setStyleSheet("padding: 4px;")
        self.qa_image_label.hide()
        qa_layout.addWidget(self.qa_image_label)
        self.qa_choices_layout = QVBoxLayout()
        qa_layout.addLayout(self.qa_choices_layout)
        self._qa_choice_labels: list[QLabel] = []
        self._qa_stat_labels: list[QLabel] = []
        # Cumulative pick-rate row, refreshed on question_start and question_end.
        self.qa_stats_summary = QLabel("")
        self.qa_stats_summary.setStyleSheet("color: #888888; font-size: 11px; padding: 2px 4px;")
        qa_layout.addWidget(self.qa_stats_summary)
        # question_id of the question currently shown in the panel; used to
        # decide which stats payload to apply when refreshes return.
        self._current_question_id: int | None = None
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
        _hdr = self.lb_table.horizontalHeader()
        for _i in range(4):
            _hdr.setSectionResizeMode(_i, QHeaderView.ResizeMode.Interactive)
        _hdr.setStretchLastSection(False)
        self.lb_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lb_layout.addWidget(self.lb_table)

        self.server_console_group = QWidget()
        srv_layout = QVBoxLayout(self.server_console_group)
        srv_layout.setContentsMargins(0, 0, 0, 0)
        srv_toolbar = QHBoxLayout()
        srv_toolbar.setContentsMargins(0, 0, 0, 0)
        srv_toolbar.addStretch()
        self.server_version_label = QLabel("Server: …")
        self.server_version_label.setStyleSheet("color: #888888; padding: 0 6px;")
        self.server_version_label.setToolTip("Version reported by GET /api/version")
        srv_toolbar.addWidget(self.server_version_label)
        srv_layout.addLayout(srv_toolbar)
        QTimer.singleShot(800, self._refresh_server_version)
        self.server_console = QPlainTextEdit()
        self.server_console.setReadOnly(True)
        self.server_console.setMaximumBlockCount(500)
        self.server_console.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; "
            "background-color: #FFFFFF; color: #333333;"
        )
        srv_layout.addWidget(self.server_console)

        space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        space_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        space_shortcut.activated.connect(self.btn_next.click)

        layout.addStretch(1)

    def _refresh_quizzes(self):
        self.quiz_combo.clear()
        self._quiz_question_counts = {}
        self._quiz_randomize_defaults = {}
        try:
            quizzes = self.api.list_quizzes()
            for qz in quizzes:
                count = qz.get("question_count", 0)
                self._quiz_question_counts[qz["id"]] = count
                self._quiz_randomize_defaults[qz["id"]] = qz.get("randomize_order", False)
                self.quiz_combo.addItem(qz["name"], qz["id"])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load quizzes: {e}")
        self._on_quiz_selection_changed()

    def _on_quiz_selection_changed(self):
        quiz_id = self.quiz_combo.currentData()
        count = self._quiz_question_counts.get(quiz_id, 0) if quiz_id is not None else 0
        if count > 0:
            self.total_questions_label.setText(f"Total questions: {count}")
            self.question_count_spin.setMaximum(count)
            self.question_count_spin.setValue(count)
            self.question_count_spin.setEnabled(True)
        else:
            self.total_questions_label.setText("Total questions: —")
            self.question_count_spin.setMaximum(1)
            self.question_count_spin.setValue(1)
            self.question_count_spin.setEnabled(False)
        randomize_default = self._quiz_randomize_defaults.get(quiz_id, False) if quiz_id is not None else False
        self.randomize_order_check.setChecked(randomize_default)

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
            self.current_join_code = game.get("join_code")
            total = self._quiz_question_counts.get(quiz_id, 0)
            selected = self.question_count_spin.value()
            question_count = selected if selected < total else None
            self.api.init_game(
                self.current_game_id,
                question_count=question_count,
                randomize_order=self.randomize_order_check.isChecked(),
            )
            code_display = self.current_join_code or str(self.current_game_id)
            self.game_label.setText(f"Game #{self.current_game_id} — Code: {code_display} (waiting)")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create game: {e}")
            return

        # Make sure the projector is showing the new game code. The window
        # is a persistent singleton — we reuse it (keeping fullscreen /
        # position) if it exists, lazily create it otherwise, and always
        # ensure it's visible at the start of a new game.
        if self.projection_window is None:
            self.projection_window = ProjectionWindow(
                game_id=self.current_game_id,
                join_code=self.current_join_code,
                server_host=self.server_host,
                server_port=self.server_port,
            )
        else:
            self.projection_window.reset_for_new_game(self.current_game_id, self.current_join_code)
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

        self.ws_thread = WebSocketThread(
            self.current_game_id,
            host=self.server_host,
            port=self.server_port,
            token=getattr(self.api, "token", None),
        )
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

        # Update the projection window FIRST for every visible-state message
        # so the projector never has to wait for slower control-panel work
        # (table rebuilds, HTTP stat fetches, log appends) running on the
        # same GUI thread. The control panel's own widgets repaint on the
        # next event-loop iteration regardless of order.
        proj = self.projection_window
        if proj is not None:
            if msg_type == "player_joined":
                proj.on_player_joined(msg)
            elif msg_type == "game_start":
                proj.on_game_start(msg)
            elif msg_type == "question_start":
                proj.on_question_start(msg)
            elif msg_type == "points_update":
                proj.on_points_update(msg)
            elif msg_type == "choice_eliminated":
                proj.on_choice_eliminated(msg)
            elif msg_type == "answer_count":
                proj.on_answer_count(msg)
            elif msg_type == "question_end":
                proj.on_question_end(msg)
            elif msg_type == "game_end":
                proj.on_game_end(msg)

        if msg_type == "player_joined":
            self.players_label.setText(f"Players: {msg.get('player_count', 0)}")
            pid = msg.get("player_id")
            name = msg.get("name", "")
            if pid is not None:
                self._players[pid] = name
            self._update_leaderboard_from_players()

        elif msg_type == "player_left":
            self.players_label.setText(f"Players: {msg.get('player_count', 0)}")
            pid = msg.get("player_id")
            self._players.pop(pid, None)
            self._update_leaderboard_from_players()

        elif msg_type == "game_start":
            self.status_label.setText("Status: Game started!")
            if self.current_game_id is not None:
                code_display = self.current_join_code or str(self.current_game_id)
                self.game_label.setText(f"Game #{self.current_game_id} — Code: {code_display} (running)")
            self.btn_start.setEnabled(False)
            self.btn_next.setEnabled(True)

        elif msg_type == "question_start":
            idx = msg.get("index", 0)
            total = msg.get("total", 0)
            self.q_label.setText(f"Question: {idx + 1} / {total}")
            self.answers_label.setText(f"Answers: 0/?")
            self.btn_next.setEnabled(False)
            self.btn_next.setText("Next Question")
            self.btn_reveal.setEnabled(True)
            # Reset per-question answer markers but keep existing scores so
            # the leaderboard persists across questions. Only the ✓/✗ column
            # clears between questions.
            self._answer_status.clear()
            self._refresh_answer_column()
            self._show_question(msg)
            qid = msg.get("question_id")
            self._current_question_id = int(qid) if qid is not None else None
            # Stats fetch hits the HTTP API synchronously; run it on a
            # worker thread so a slow response can't freeze the projector.
            self._fetch_question_stats_async(self._current_question_id)

        elif msg_type == "question_answer":
            self._highlight_correct(msg.get("correct_answer", ""))

        elif msg_type == "points_update":
            remaining = msg.get("time_remaining_ms", 0)
            secs = remaining / 1000
            self.time_label.setText(f"Time: {secs:.1f}s | Pts: {msg.get('current_points', 0)}")

        elif msg_type == "player_answered":
            pid = msg.get("player_id")
            if pid is not None:
                self._answer_status[pid] = bool(msg.get("is_correct", False))
                self._refresh_answer_column()

        elif msg_type == "answer_count":
            self.answers_label.setText(f"Answers: {msg.get('answered', 0)}/{msg.get('total', 0)}")

        elif msg_type == "question_end":
            self.btn_reveal.setEnabled(False)
            self.btn_next.setEnabled(True)
            self.time_label.setText("Time: -")
            self._update_leaderboard(msg.get("player_scores", []))
            # Refresh the cumulative pick rates so this round's answers show.
            self._fetch_question_stats_async(self._current_question_id)

        elif msg_type == "game_end":
            self.status_label.setText("Status: Game finished!")
            self.game_label.setText("No active game")
            self.current_game_id = None
            self.btn_next.setEnabled(False)
            self.btn_reveal.setEnabled(False)
            self.btn_end.setEnabled(False)
            # Keep the leaderboard and player list visible after the game
            # ends so the instructor can review results. Everything is
            # cleared by _reset_ui_for_new_game() when the next game starts.
            self._answer_status.clear()
            self._refresh_answer_column()
            self._clear_question()

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
                server_host=self.server_host,
                server_port=self.server_port,
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
        self.lb_table.resizeColumnsToContents()

    def _show_question(self, msg: dict):
        self.qa_question_label.setText(msg.get("text", ""))
        image_url = msg.get("image_url")
        self._current_image_url = image_url
        self.qa_image_label.hide()
        if image_url:
            self._fetch_image_async(image_url)
        # Clear old choice + stat labels
        self._clear_choice_rows()
        # Add new choice labels with a paired stat label on the right
        for choice in msg.get("choices", []):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(f"  {choice}")
            lbl.setStyleSheet("font-size: 13px; padding: 2px 8px; border-radius: 4px;")
            stat = QLabel("")
            stat.setStyleSheet("color: #888888; font-size: 12px; padding: 2px 8px;")
            stat.setMinimumWidth(80)
            stat.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl, 1)
            row.addWidget(stat)
            container = QWidget()
            container.setLayout(row)
            self.qa_choices_layout.addWidget(container)
            self._qa_choice_labels.append(lbl)
            self._qa_stat_labels.append(stat)
        self.qa_stats_summary.setText("")

    def _clear_choice_rows(self):
        """Remove all choice/stat rows from qa_choices_layout."""
        while self.qa_choices_layout.count():
            item = self.qa_choices_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._qa_choice_labels.clear()
        self._qa_stat_labels.clear()

    @staticmethod
    def _strip_choice_label(text: str) -> str:
        text = text.strip()
        if len(text) > 3 and text[0] in "ABCD" and text[1:3] == ") ":
            return text[3:]
        return text

    def _fetch_image_async(self, image_url: str) -> None:
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
            self.qa_image_label.hide()
            return
        pixmap = QPixmap()
        pixmap.loadFromData(data)
        if pixmap.isNull():
            self.qa_image_label.hide()
            return
        max_h = 180
        if pixmap.height() > max_h:
            pixmap = pixmap.scaledToHeight(max_h, Qt.TransformationMode.SmoothTransformation)
        self.qa_image_label.setPixmap(pixmap)
        self.qa_image_label.show()

    def _fetch_question_stats_async(self, question_id: int | None) -> None:
        """Fetch cumulative pick rates on a worker thread and emit the result
        back to the GUI thread via ``_stats_loaded``.

        Doing the HTTP roundtrip on the GUI thread (as the previous
        ``_load_question_stats`` did) blocked rendering for the duration of
        the request, which made the projection window visibly stutter on
        every question_start / question_end. ``threading.Thread`` is enough
        here — pyqtSignal.emit() is thread-safe and the connection is queued
        across threads, so the slot runs on the GUI thread.
        """
        if question_id is None:
            return
        target = int(question_id)

        def _worker() -> None:
            try:
                stats = self.api.get_question_stats(target)
            except Exception as e:
                print(f"[INSTR] question stats unavailable: {e}")
                return
            if not isinstance(stats, dict):
                return
            self._stats_loaded.emit(target, stats)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_stats_loaded(self, question_id: int, stats: dict) -> None:
        """GUI-thread slot: render stats fetched by the worker thread.

        Discards results that arrive after the user has moved on to a
        different question so a slow response can't overwrite a freshly-
        shown one.
        """
        if self._current_question_id != question_id:
            return
        counts = stats.get("counts", {}) or {}
        percentages = stats.get("percentages", {}) or {}
        total = int(stats.get("total", 0) or 0)
        for lbl, stat in zip(self._qa_choice_labels, self._qa_stat_labels):
            key = self._strip_choice_label(lbl.text())
            count = int(counts.get(key, 0) or 0)
            pct = float(percentages.get(key, 0.0) or 0.0)
            if total == 0:
                stat.setText("—")
            else:
                stat.setText(f"{pct:.0f}% ({count})")
        non_responses = int(stats.get("non_responses", 0) or 0)
        non_pct = float(stats.get("non_response_percentage", 0.0) or 0.0)
        if total == 0:
            self.qa_stats_summary.setText("No prior responses recorded for this question.")
        else:
            parts = [
                "Cumulative pick rate across all sessions",
                f"total: {total}",
                f"no response: {non_responses} ({non_pct:.0f}%)",
            ]
            self.qa_stats_summary.setText("  ·  ".join(parts))

    def _highlight_correct(self, correct: str):
        for lbl in self._qa_choice_labels:
            text = lbl.text().strip()
            if text == correct:
                lbl.setStyleSheet(
                    "font-size: 13px; padding: 2px 8px; border-radius: 4px; "
                    "background-color: #C8E6C9; color: #2E7D32; font-weight: bold;"
                )

    def _clear_question(self):
        self.qa_question_label.setText("")
        self.qa_image_label.hide()
        self.qa_image_label.clear()
        self._current_image_url = None
        self._clear_choice_rows()
        self.qa_stats_summary.setText("")
        self._current_question_id = None

    def _update_leaderboard_from_players(self):
        """Show all joined players with score 0, sorted by name."""
        items = sorted(self._players.items(), key=lambda kv: kv[1].lower())
        self.lb_table.setRowCount(len(items))
        for row, (pid, name) in enumerate(items):
            self.lb_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.lb_table.setItem(row, 1, QTableWidgetItem(name))
            self.lb_table.setItem(row, 3, QTableWidgetItem("0"))
            self._set_answer_cell(row, self._answer_status.get(pid))
        self.lb_table.resizeColumnsToContents()

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

    # ── Server log stream ─────────────────────────────────────────────────

    def _connect_log_ws(self):
        self._log_ws = LogWebSocketThread(
            self.server_host, self.server_port,
            token=getattr(self.api, "token", None),
        )
        self._log_ws.line_received.connect(self._append_server_log)
        self._log_ws.status_changed.connect(self._append_server_log)
        self._log_ws.start()

    def _append_server_log(self, line: str):
        self.server_console.appendPlainText(line)
        sb = self.server_console.verticalScrollBar()
        sb.setValue(sb.maximum())


    # ── Server version ─────────────────────────────────────────────────────────────

    def _refresh_server_version(self) -> None:
        """Poll /api/version on a worker thread to avoid blocking the GUI."""
        http_scheme = "https" if self.server_port == 443 else "http"
        url = f"{http_scheme}://{self.server_host}:{self.server_port}/api/version"

        def _worker() -> None:
            try:
                import httpx
                r = httpx.get(url, timeout=1.0)
                if r.status_code == 200:
                    v = r.json().get("version", "?")
                    self._version_loaded.emit(f"Server: v{v}", "color: #2E7D32; padding: 0 6px;")
                    return
            except Exception:
                pass
            self._version_loaded.emit("Server: offline", "color: #E53935; padding: 0 6px;")

        threading.Thread(target=_worker, daemon=True).start()

    def _on_version_loaded(self, text: str, style: str) -> None:
        self.server_version_label.setText(text)
        self.server_version_label.setStyleSheet(style)

    # ── Active games poll ──────────────────────────────────────────────────────

    def _poll_active_games(self) -> None:
        http_scheme = "https" if self.server_port == 443 else "http"
        url = f"{http_scheme}://{self.server_host}:{self.server_port}/api/status"

        def _worker() -> None:
            try:
                import httpx
                r = httpx.get(url, timeout=1.0)
                if r.status_code == 200:
                    self._status_polled.emit(r.json().get("active_games", 0))
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _on_status_polled(self, count: int) -> None:
        self.active_games_label.setText(f"Active games: {count}")
        style = "font-size: 13px; color: #2E7D32;" if count > 0 else "font-size: 13px; color: #888888;"
        self.active_games_label.setStyleSheet(style)

    def closeEvent(self, event):
        if self._log_ws:
            self._log_ws.stop()
            self._log_ws.wait(2000)
        if self.ws_thread:
            self.ws_thread.stop()
            self.ws_thread.wait(2000)
        if self.projection_window:
            self.projection_window.close()
        event.accept()
