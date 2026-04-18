import json
import threading

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread

from instructor.api_client import ApiClient
from instructor.games.pointdrop.display_window import DisplayWindow

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

    def __init__(self, session_id: int, host: str = "localhost", port: int = 5000):
        super().__init__()
        self.session_id = session_id
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
        uri = f"ws://{self.host}:{self.port}/ws/instructor/{self.session_id}"
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
                        print(f"[INSTR-WS] Received: {data.get('type', '?')}")
                        self.message_received.emit(data)
                    except asyncio.TimeoutError:
                        continue
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


class PointDropControlPanel(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self.ws_thread: WebSocketThread | None = None
        self.display_window: DisplayWindow | None = None
        self.current_session_id: int | None = None
        self._players: dict[int, str] = {}  # player_id -> name
        self._build_ui()
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
        row1.addWidget(QLabel("Quiz:"))
        row1.addWidget(self.quiz_combo)
        row1.addWidget(btn_refresh)
        row1.addStretch()
        setup_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.btn_create_session = QPushButton("Create Session")
        self.btn_create_session.clicked.connect(self._create_session)
        self.session_label = QLabel("No active session")
        self.session_label.setStyleSheet("font-weight: bold;")
        row2.addWidget(self.btn_create_session)
        row2.addWidget(self.session_label)
        row2.addStretch()
        setup_layout.addLayout(row2)

        layout.addWidget(setup_group)

        # ── Controls Group ─────────────────────────────────────────────────
        controls_group = QGroupBox("Game Controls")
        controls_layout = QVBoxLayout(controls_group)

        self.status_label = QLabel("Status: Not connected")
        self.status_label.setStyleSheet("font-size: 14px;")
        controls_layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Start Game")
        self.btn_start.clicked.connect(self._start_game)
        self.btn_start.setEnabled(False)
        self.btn_next = QPushButton("Next Question")
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

        # ── Display Window Button ──────────────────────────────────────────
        display_row = QHBoxLayout()
        self.btn_display = QPushButton("Open Display Window")
        self.btn_display.clicked.connect(self._toggle_display)
        self.btn_display.setEnabled(False)
        display_row.addWidget(self.btn_display)
        display_row.addStretch()
        layout.addLayout(display_row)

        # ── Leaderboard ───────────────────────────────────────────────────
        lb_group = QGroupBox("Live Leaderboard")
        lb_layout = QVBoxLayout(lb_group)
        self.lb_table = QTableWidget()
        self.lb_table.setColumnCount(3)
        self.lb_table.setHorizontalHeaderLabels(["Rank", "Name", "Score"])
        self.lb_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.lb_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lb_layout.addWidget(self.lb_table)
        layout.addWidget(lb_group)

    def _refresh_quizzes(self):
        self.quiz_combo.clear()
        try:
            quizzes = self.api.list_quizzes()
            for qz in quizzes:
                self.quiz_combo.addItem(f"{qz['name']} ({qz.get('question_count', 0)} Q's)", qz["id"])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load quizzes: {e}")

    def _create_session(self):
        quiz_id = self.quiz_combo.currentData()
        if quiz_id is None:
            QMessageBox.warning(self, "Error", "Select a quiz first.")
            return

        try:
            session = self.api.create_session(quiz_id)
            self.current_session_id = session["id"]
            self.api.init_game(self.current_session_id)
            self.session_label.setText(f"Session #{self.current_session_id} (waiting)")
            self._connect_ws()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create session: {e}")

    def _connect_ws(self):
        if not HAS_WEBSOCKETS:
            QMessageBox.warning(self, "Error", "websockets package not installed")
            return
        if self.current_session_id is None:
            return

        self.ws_thread = WebSocketThread(self.current_session_id)
        self.ws_thread.message_received.connect(self._on_ws_message)
        self.ws_thread.connected.connect(self._on_ws_connected)
        self.ws_thread.disconnected.connect(self._on_ws_disconnected)
        self.ws_thread.start()

    def _on_ws_connected(self):
        self.status_label.setText("Status: Connected (waiting for players)")
        self.btn_start.setEnabled(True)
        self.btn_end.setEnabled(True)
        self.btn_display.setEnabled(True)

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
            if self.display_window:
                self.display_window.on_player_joined(msg)

        elif msg_type == "player_left":
            self.players_label.setText(f"Players: {msg.get('player_count', 0)}")
            pid = msg.get("player_id")
            self._players.pop(pid, None)
            self._update_leaderboard_from_players()

        elif msg_type == "game_start":
            self.status_label.setText("Status: Game started!")
            self.btn_start.setEnabled(False)
            self.btn_next.setEnabled(True)
            if self.display_window:
                self.display_window.on_game_start(msg)

        elif msg_type == "question_start":
            idx = msg.get("index", 0)
            total = msg.get("total", 0)
            self.q_label.setText(f"Question: {idx + 1} / {total}")
            self.answers_label.setText(f"Answers: 0/?")
            self.btn_next.setEnabled(False)
            self.btn_reveal.setEnabled(True)
            if self.display_window:
                self.display_window.on_question_start(msg)

        elif msg_type == "points_update":
            remaining = msg.get("time_remaining_ms", 0)
            secs = remaining / 1000
            self.time_label.setText(f"Time: {secs:.1f}s | Pts: {msg.get('current_points', 0)}")
            if self.display_window:
                self.display_window.on_points_update(msg)

        elif msg_type == "choice_eliminated":
            if self.display_window:
                self.display_window.on_choice_eliminated(msg)

        elif msg_type == "answer_count":
            self.answers_label.setText(f"Answers: {msg.get('answered', 0)}/{msg.get('total', 0)}")
            if self.display_window:
                self.display_window.on_answer_count(msg)

        elif msg_type == "question_end":
            self.btn_reveal.setEnabled(False)
            self.btn_next.setEnabled(True)
            self.time_label.setText("Time: -")
            self._update_leaderboard(msg.get("player_scores", []))
            if self.display_window:
                self.display_window.on_question_end(msg)

        elif msg_type == "game_end":
            self.status_label.setText("Status: Game finished!")
            self.btn_next.setEnabled(False)
            self.btn_reveal.setEnabled(False)
            self.btn_end.setEnabled(False)
            self._players.clear()
            self.lb_table.setRowCount(0)
            if self.display_window:
                self.display_window.on_game_end(msg)

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

    def _toggle_display(self):
        if self.display_window and self.display_window.isVisible():
            self.display_window.close()
            self.display_window = None
            self.btn_display.setText("Open Display Window")
        else:
            self.display_window = DisplayWindow(
                session_id=self.current_session_id,
                server_port=5000,
            )
            self.display_window.show()
            self.btn_display.setText("Close Display Window")

    def _update_leaderboard(self, scores: list[dict]):
        self.lb_table.setRowCount(len(scores))
        for row, s in enumerate(scores):
            rank = s.get("rank", row + 1)
            self.lb_table.setItem(row, 0, QTableWidgetItem(str(rank)))
            self.lb_table.setItem(row, 1, QTableWidgetItem(s.get("name", "")))
            score = s.get("total_score", 0)
            self.lb_table.setItem(row, 2, QTableWidgetItem(str(score)))

    def _update_leaderboard_from_players(self):
        """Show all joined players with score 0, sorted by name."""
        names = sorted(self._players.values(), key=str.lower)
        self.lb_table.setRowCount(len(names))
        for row, name in enumerate(names):
            self.lb_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.lb_table.setItem(row, 1, QTableWidgetItem(name))
            self.lb_table.setItem(row, 2, QTableWidgetItem("0"))

    def closeEvent(self, event):
        if self.ws_thread:
            self.ws_thread.stop()
            self.ws_thread.wait(2000)
        if self.display_window:
            self.display_window.close()
        event.accept()
