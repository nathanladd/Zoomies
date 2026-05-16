from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QMessageBox, QHeaderView, QDialog,
    QDialogButtonBox, QFormLayout, QLineEdit, QTextEdit, QCheckBox,
    QSplitter, QListWidget, QListWidgetItem, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from instructor.api_client import ApiClient


class QuizDialog(QDialog):
    def __init__(self, parent=None, quiz=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Quiz" if quiz else "New Quiz")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Quiz name")
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Optional description")
        self.desc_input.setMaximumHeight(80)
        self.randomize_check = QCheckBox("Randomize question order each game")

        if quiz:
            self.name_input.setText(quiz.get("name", ""))
            self.desc_input.setText(quiz.get("description", "") or "")
            self.randomize_check.setChecked(quiz.get("randomize_order", False))

        layout.addRow("Name:", self.name_input)
        layout.addRow("Description:", self.desc_input)
        layout.addRow(self.randomize_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "description": self.desc_input.toPlainText().strip() or None,
            "randomize_order": self.randomize_check.isChecked(),
        }


class QuizBuilder(QWidget):
    edit_question_requested = pyqtSignal(int)  # emits question_id

    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self.current_quiz_id: int | None = None
        self._build_ui()
        self.refresh_quizzes()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: Quiz list ────────────────────────────────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        quiz_toolbar = QHBoxLayout()
        self.btn_new_quiz = QPushButton("+ New Quiz")
        self.btn_new_quiz.clicked.connect(self.create_quiz)
        self.btn_edit_quiz = QPushButton("Edit")
        self.btn_edit_quiz.clicked.connect(self.edit_quiz)
        self.btn_del_quiz = QPushButton("Delete")
        self.btn_del_quiz.clicked.connect(self.delete_quiz)
        quiz_toolbar.addWidget(self.btn_new_quiz)
        quiz_toolbar.addWidget(self.btn_edit_quiz)
        quiz_toolbar.addWidget(self.btn_del_quiz)
        left_layout.addLayout(quiz_toolbar)

        self.quiz_table = QTableWidget()
        self.quiz_table.setColumnCount(3)
        self.quiz_table.setHorizontalHeaderLabels(["ID", "Name", "Questions"])
        _hdr = self.quiz_table.horizontalHeader()
        for _i in range(3):
            _hdr.setSectionResizeMode(_i, QHeaderView.ResizeMode.ResizeToContents)
        _hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.quiz_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.quiz_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.quiz_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.quiz_table.currentCellChanged.connect(self._on_quiz_selected)
        left_layout.addWidget(self.quiz_table)

        # ── Right: Quiz questions ──────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.quiz_detail_label = QLabel("Select a quiz to view its questions")
        self.quiz_detail_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(self.quiz_detail_label)

        q_toolbar = QHBoxLayout()
        self.btn_add_q = QPushButton("+ Add Question")
        self.btn_add_q.clicked.connect(self.add_question)
        self.btn_remove_q = QPushButton("Remove")
        self.btn_remove_q.clicked.connect(self.remove_question)
        self.btn_move_up = QPushButton("Move Up")
        self.btn_move_up.clicked.connect(self.move_up)
        self.btn_move_down = QPushButton("Move Down")
        self.btn_move_down.clicked.connect(self.move_down)
        q_toolbar.addWidget(self.btn_add_q)
        q_toolbar.addWidget(self.btn_remove_q)
        q_toolbar.addWidget(self.btn_move_up)
        q_toolbar.addWidget(self.btn_move_down)
        right_layout.addLayout(q_toolbar)

        self.q_table = QTableWidget()
        self.q_table.setColumnCount(5)
        self.q_table.setHorizontalHeaderLabels(["#", "Q-ID", "Type", "Text", "Time"])
        _hdr = self.q_table.horizontalHeader()
        for _i in range(5):
            _hdr.setSectionResizeMode(_i, QHeaderView.ResizeMode.ResizeToContents)
        _hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.q_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.q_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.q_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.q_table.doubleClicked.connect(self._on_question_double_clicked)
        right_layout.addWidget(self.q_table)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([350, 550])

        layout.addWidget(splitter)

    def refresh_quizzes(self):
        try:
            quizzes = self.api.list_quizzes()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load quizzes: {e}")
            return

        self.quiz_table.setRowCount(len(quizzes))
        for row, qz in enumerate(quizzes):
            self.quiz_table.setItem(row, 0, QTableWidgetItem(str(qz["id"])))
            self.quiz_table.setItem(row, 1, QTableWidgetItem(qz["name"]))
            self.quiz_table.setItem(row, 2, QTableWidgetItem(str(qz.get("question_count", 0))))

    def _on_quiz_selected(self, row, col, prev_row, prev_col):
        if row < 0:
            return
        qid = int(self.quiz_table.item(row, 0).text())
        self.current_quiz_id = qid
        self._load_quiz_questions(qid)

    def _load_quiz_questions(self, quiz_id: int):
        try:
            quiz = self.api.get_quiz(quiz_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        self.quiz_detail_label.setText(f"Quiz: {quiz['name']}")
        questions = quiz.get("questions", [])

        self.q_table.setRowCount(len(questions))
        for row, qq in enumerate(questions):
            self.q_table.setItem(row, 0, QTableWidgetItem(str(qq["position"])))
            self.q_table.setItem(row, 1, QTableWidgetItem(str(qq["question_id"])))
            q = qq.get("question") or {}
            self.q_table.setItem(row, 2, QTableWidgetItem(q.get("question_type", "")))
            text = (q.get("text") or "")[:60]
            self.q_table.setItem(row, 3, QTableWidgetItem(text))
            self.q_table.setItem(row, 4, QTableWidgetItem(f"{q.get('time_seconds', 10)}s"))

    def _on_question_double_clicked(self):
        row = self.q_table.currentRow()
        if row < 0:
            return
        qid = int(self.q_table.item(row, 1).text())
        self.edit_question_requested.emit(qid)

    def create_quiz(self):
        dlg = QuizDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Error", "Name is required.")
                return
            try:
                self.api.create_quiz(**data)
                self.refresh_quizzes()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create quiz: {e}")

    def edit_quiz(self):
        if self.current_quiz_id is None:
            QMessageBox.information(self, "Info", "Select a quiz first.")
            return
        try:
            quiz = self.api.get_quiz(self.current_quiz_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        dlg = QuizDialog(self, quiz)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                self.api.update_quiz(self.current_quiz_id, **data)
                self.refresh_quizzes()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update quiz: {e}")

    def delete_quiz(self):
        if self.current_quiz_id is None:
            QMessageBox.information(self, "Info", "Select a quiz first.")
            return
        reply = QMessageBox.question(
            self, "Confirm", "Delete this quiz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.api.delete_quiz(self.current_quiz_id)
                self.current_quiz_id = None
                self.q_table.setRowCount(0)
                self.quiz_detail_label.setText("Select a quiz to view its questions")
                self.refresh_quizzes()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete quiz: {e}")

    def add_question(self):
        if self.current_quiz_id is None:
            QMessageBox.information(self, "Info", "Select a quiz first.")
            return

        dlg = AddQuestionDialog(self.api, self)
        dlg.questionPicked.connect(self._on_question_picked)
        dlg.show()

    def _on_question_picked(self, qid: int):
        if self.current_quiz_id is None:
            return
        try:
            self.api.add_question_to_quiz(self.current_quiz_id, qid)
            self._load_quiz_questions(self.current_quiz_id)
            self.refresh_quizzes()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add question: {e}")

    def remove_question(self):
        if self.current_quiz_id is None:
            return
        row = self.q_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Info", "Select a question to remove.")
            return
        qid = int(self.q_table.item(row, 1).text())
        try:
            self.api.remove_question_from_quiz(self.current_quiz_id, qid)
            self._load_quiz_questions(self.current_quiz_id)
            self.refresh_quizzes()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to remove question: {e}")

    def move_up(self):
        self._swap(-1)

    def move_down(self):
        self._swap(1)

    def _swap(self, direction: int):
        if self.current_quiz_id is None:
            return
        row = self.q_table.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.q_table.rowCount():
            return

        # Collect current order
        ids = []
        for r in range(self.q_table.rowCount()):
            ids.append(int(self.q_table.item(r, 1).text()))
        ids[row], ids[new_row] = ids[new_row], ids[row]

        try:
            self.api.reorder_quiz_questions(self.current_quiz_id, ids)
            self._load_quiz_questions(self.current_quiz_id)
            self.q_table.setCurrentCell(new_row, 0)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to reorder: {e}")


class AddQuestionDialog(QDialog):
    """Non-modal dialog to pick questions from the pool and add them to a quiz.

    Stays open across adds so the user can queue up multiple questions. Emits
    ``questionPicked`` every time the user confirms a selection (via the Add
    button or a double-click on a row).
    """

    questionPicked = pyqtSignal(int)

    def __init__(self, api: ApiClient, parent=None):
        super().__init__(parent)
        self.api = api
        self.setWindowTitle("Add Questions to Quiz")
        self.setMinimumSize(600, 400)
        # Non-modal so the quiz builder panel can live-update behind it.
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)

        # Filter
        filter_row = QHBoxLayout()
        self.topic_filter = QComboBox()
        self.topic_filter.addItem("All Topics", None)
        try:
            for t in api.list_topics():
                self.topic_filter.addItem(t["name"], t["id"])
        except Exception:
            pass
        self.topic_filter.currentIndexChanged.connect(self._load_questions)
        filter_row.addWidget(QLabel("Topic:"))
        filter_row.addWidget(self.topic_filter)
        filter_row.addStretch()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._load_questions)
        filter_row.addWidget(self.btn_refresh)
        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Type", "Text", "Topic"])
        _hdr = self.table.horizontalHeader()
        for _i in range(4):
            _hdr.setSectionResizeMode(_i, QHeaderView.ResizeMode.ResizeToContents)
        _hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._emit_selected)
        layout.addWidget(self.table)

        self.status_label = QLabel("Double-click a question or select one and click Add.")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_add = QPushButton("Add")
        self.btn_add.setDefault(True)
        self.btn_add.clicked.connect(self._emit_selected)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        self._load_questions()

    def _load_questions(self):
        tid = self.topic_filter.currentData()
        try:
            questions = self.api.list_questions(topic_id=tid)
        except Exception:
            questions = []

        self.table.setRowCount(len(questions))
        for row, q in enumerate(questions):
            self.table.setItem(row, 0, QTableWidgetItem(str(q["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(q["question_type"]))
            self.table.setItem(row, 2, QTableWidgetItem((q.get("text") or "")[:60]))
            self.table.setItem(row, 3, QTableWidgetItem(q.get("topic_name") or "-"))

    def _selected_question_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        return int(item.text())

    def _emit_selected(self, *_):
        qid = self._selected_question_id()
        if qid is None:
            self.status_label.setText("Select a question first.")
            return
        row = self.table.currentRow()
        text_item = self.table.item(row, 2)
        preview = text_item.text() if text_item else f"#{qid}"
        self.questionPicked.emit(qid)
        self.status_label.setText(f"Added: {preview}")
