from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QMessageBox, QHeaderView, QTabWidget,
    QComboBox, QLineEdit,
)
from PyQt6.QtCore import Qt

from instructor.api_client import ApiClient


class ResultsViewer(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_sessions_tab(), "Session Results")
        tabs.addTab(self._build_questions_tab(), "Question Analytics")
        tabs.addTab(self._build_students_tab(), "Student History")
        layout.addWidget(tabs)

    # ── Session Results ────────────────────────────────────────────────────

    def _build_sessions_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        toolbar = QHBoxLayout()
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(250)
        btn_load = QPushButton("Load Results")
        btn_load.clicked.connect(self._load_session_results)
        btn_refresh_sessions = QPushButton("Refresh Sessions")
        btn_refresh_sessions.clicked.connect(self._refresh_session_list)
        toolbar.addWidget(QLabel("Session:"))
        toolbar.addWidget(self.session_combo)
        toolbar.addWidget(btn_load)
        toolbar.addStretch()
        toolbar.addWidget(btn_refresh_sessions)
        layout.addLayout(toolbar)

        self.session_info = QLabel("")
        self.session_info.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.session_info)

        self.players_table = QTableWidget()
        self.players_table.setColumnCount(4)
        self.players_table.setHorizontalHeaderLabels(["Rank", "Name", "Score", "Joined"])
        self.players_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.players_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.players_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.players_table)

        self._refresh_session_list()
        return w

    def _refresh_session_list(self):
        self.session_combo.clear()
        try:
            sessions = self.api.list_sessions()
            for s in sessions:
                label = f"#{s['id']} - {s.get('quiz_name', 'Unknown')} ({s['status']})"
                self.session_combo.addItem(label, s["id"])
        except Exception:
            pass

    def _load_session_results(self):
        sid = self.session_combo.currentData()
        if sid is None:
            return
        try:
            data = self.api.get_session_results(sid)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load results: {e}")
            return

        session = data["session"]
        self.session_info.setText(
            f"Quiz: {session.get('quiz_name', '?')} | Status: {session['status']} | "
            f"Players: {session.get('player_count', 0)} | Game: {session['game_type']}"
        )

        players = data["players"]
        self.players_table.setRowCount(len(players))
        for row, p in enumerate(players):
            self.players_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.players_table.setItem(row, 1, QTableWidgetItem(p["name"]))
            self.players_table.setItem(row, 2, QTableWidgetItem(str(p["total_score"])))
            self.players_table.setItem(row, 3, QTableWidgetItem(p.get("joined_at", "")))

    # ── Question Analytics ─────────────────────────────────────────────────

    def _build_questions_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        toolbar = QHBoxLayout()
        btn_load = QPushButton("Load Analytics")
        btn_load.clicked.connect(self._load_question_analytics)
        toolbar.addWidget(btn_load)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.analytics_table = QTableWidget()
        self.analytics_table.setColumnCount(5)
        self.analytics_table.setHorizontalHeaderLabels([
            "Q-ID", "Text", "Times Asked", "Accuracy %", "Avg Time (ms)",
        ])
        self.analytics_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.analytics_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.analytics_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.analytics_table)

        return w

    def _load_question_analytics(self):
        try:
            data = self.api.get_question_analytics()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load analytics: {e}")
            return

        self.analytics_table.setRowCount(len(data))
        for row, qa in enumerate(data):
            self.analytics_table.setItem(row, 0, QTableWidgetItem(str(qa["question_id"])))
            self.analytics_table.setItem(row, 1, QTableWidgetItem((qa.get("question_text") or "")[:60]))
            self.analytics_table.setItem(row, 2, QTableWidgetItem(str(qa["times_asked"])))
            self.analytics_table.setItem(row, 3, QTableWidgetItem(f"{qa['accuracy_pct']}%"))
            self.analytics_table.setItem(row, 4, QTableWidgetItem(str(int(qa["avg_response_time_ms"]))))

    # ── Student History ────────────────────────────────────────────────────

    def _build_students_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        toolbar = QHBoxLayout()
        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Search student name...")
        btn_search = QPushButton("Search")
        btn_search.clicked.connect(self._search_student)
        btn_all = QPushButton("Show All")
        btn_all.clicked.connect(self._load_all_students)
        toolbar.addWidget(self.student_search)
        toolbar.addWidget(btn_search)
        toolbar.addWidget(btn_all)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.students_table = QTableWidget()
        self.students_table.setColumnCount(4)
        self.students_table.setHorizontalHeaderLabels(["Name", "Sessions", "Total Score", "Avg Score"])
        self.students_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.students_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.students_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.students_table)

        return w

    def _search_student(self):
        name = self.student_search.text().strip()
        if not name:
            return
        try:
            data = self.api.get_student_history(name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Student not found: {e}")
            return

        self.students_table.setRowCount(1)
        self.students_table.setItem(0, 0, QTableWidgetItem(data["name"]))
        self.students_table.setItem(0, 1, QTableWidgetItem(str(data["sessions_played"])))
        self.students_table.setItem(0, 2, QTableWidgetItem(str(data["total_score"])))
        self.students_table.setItem(0, 3, QTableWidgetItem(str(data["avg_score"])))

    def _load_all_students(self):
        try:
            data = self.api.list_student_histories()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load students: {e}")
            return

        self.students_table.setRowCount(len(data))
        for row, s in enumerate(data):
            self.students_table.setItem(row, 0, QTableWidgetItem(s["name"]))
            self.students_table.setItem(row, 1, QTableWidgetItem(str(s["sessions_played"])))
            self.students_table.setItem(row, 2, QTableWidgetItem(str(s["total_score"])))
            self.students_table.setItem(row, 3, QTableWidgetItem(str(s["avg_score"])))
