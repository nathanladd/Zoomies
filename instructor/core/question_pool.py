from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QTextEdit, QLabel, QMessageBox,
    QHeaderView, QDialog, QDialogButtonBox, QFormLayout, QComboBox,
    QSlider, QFileDialog, QGroupBox,
)
from PyQt6.QtCore import Qt

from instructor.api_client import ApiClient


class QuestionDialog(QDialog):
    def __init__(self, api: ApiClient, parent=None, question=None):
        super().__init__(parent)
        self.api = api
        self.question = question
        self.setWindowTitle("Edit Question" if question else "New Question")
        self.setMinimumWidth(550)

        layout = QFormLayout(self)

        # Question type
        self.type_combo = QComboBox()
        self.type_combo.addItems(["multiple_choice", "true_false", "technician_ab"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        layout.addRow("Type:", self.type_combo)

        # Topic
        self.topic_combo = QComboBox()
        self.topic_combo.addItem("(No topic)", None)
        try:
            topics = api.list_topics()
            for t in topics:
                self.topic_combo.addItem(t["name"], t["id"])
        except Exception:
            pass
        layout.addRow("Topic:", self.topic_combo)

        # Text
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Question text (optional if image-only)")
        self.text_input.setMaximumHeight(80)
        layout.addRow("Text:", self.text_input)

        # Answers
        self.correct_input = QLineEdit()
        self.correct_input.setPlaceholderText("Correct answer")
        self.wrong1_input = QLineEdit()
        self.wrong1_input.setPlaceholderText("Wrong answer 1")
        self.wrong2_input = QLineEdit()
        self.wrong2_input.setPlaceholderText("Wrong answer 2")
        self.wrong3_input = QLineEdit()
        self.wrong3_input.setPlaceholderText("Wrong answer 3")

        layout.addRow("Correct:", self.correct_input)
        layout.addRow("Wrong 1:", self.wrong1_input)
        layout.addRow("Wrong 2:", self.wrong2_input)
        layout.addRow("Wrong 3:", self.wrong3_input)

        # Time slider
        time_row = QHBoxLayout()
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(5, 30)
        self.time_slider.setValue(10)
        self.time_slider.setTickInterval(5)
        self.time_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.time_label = QLabel("10s")
        self.time_slider.valueChanged.connect(lambda v: self.time_label.setText(f"{v}s"))
        time_row.addWidget(self.time_slider)
        time_row.addWidget(self.time_label)
        layout.addRow("Time:", time_row)

        # Populate if editing
        if question:
            self.type_combo.setCurrentText(question.get("question_type", "multiple_choice"))
            tid = question.get("topic_id")
            if tid:
                idx = self.topic_combo.findData(tid)
                if idx >= 0:
                    self.topic_combo.setCurrentIndex(idx)
            self.text_input.setText(question.get("text", "") or "")
            self.correct_input.setText(question.get("correct_answer", ""))
            self.wrong1_input.setText(question.get("wrong_answer_1", ""))
            self.wrong2_input.setText(question.get("wrong_answer_2", "") or "")
            self.wrong3_input.setText(question.get("wrong_answer_3", "") or "")
            self.time_slider.setValue(question.get("time_seconds", 10))

        self._on_type_changed(self.type_combo.currentText())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_type_changed(self, qtype: str):
        if qtype == "true_false":
            self.correct_input.setText("True")
            self.wrong1_input.setText("False")
            self.wrong2_input.clear()
            self.wrong3_input.clear()
            self.wrong2_input.setEnabled(False)
            self.wrong3_input.setEnabled(False)
            self.correct_input.setEnabled(False)
            self.wrong1_input.setEnabled(False)
        elif qtype == "technician_ab":
            self.correct_input.setEnabled(True)
            self.correct_input.setPlaceholderText("A, B, C, or D")
            self.wrong1_input.setText("(auto)")
            self.wrong1_input.setEnabled(False)
            self.wrong2_input.clear()
            self.wrong2_input.setEnabled(False)
            self.wrong3_input.clear()
            self.wrong3_input.setEnabled(False)
        else:
            self.correct_input.setEnabled(True)
            self.wrong1_input.setEnabled(True)
            self.wrong2_input.setEnabled(True)
            self.wrong3_input.setEnabled(True)
            self.correct_input.setPlaceholderText("Correct answer")

    def get_data(self) -> dict:
        qtype = self.type_combo.currentText()
        topic_id = self.topic_combo.currentData()

        data = {
            "question_type": qtype,
            "topic_id": topic_id,
            "text": self.text_input.toPlainText().strip() or None,
            "correct_answer": self.correct_input.text().strip(),
            "wrong_answer_1": self.wrong1_input.text().strip(),
            "time_seconds": self.time_slider.value(),
        }

        if qtype == "true_false":
            data["correct_answer"] = "True" if data["correct_answer"].lower() in ("true", "t", "yes") else "False"
            data["wrong_answer_1"] = "True" if data["correct_answer"] == "False" else "False"
            data["wrong_answer_2"] = None
            data["wrong_answer_3"] = None
        elif qtype == "technician_ab":
            choices = [
                "Technician A only", "Technician B only",
                "Both Technician A and Technician B",
                "Neither Technician A nor Technician B",
            ]
            correct_letter = data["correct_answer"].upper()
            letter_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            idx = letter_map.get(correct_letter, 0)
            data["correct_answer"] = correct_letter
            wrong = [c for i, c in enumerate(choices) if i != idx]
            data["wrong_answer_1"] = wrong[0] if len(wrong) > 0 else ""
            data["wrong_answer_2"] = wrong[1] if len(wrong) > 1 else None
            data["wrong_answer_3"] = wrong[2] if len(wrong) > 2 else None
        else:
            data["wrong_answer_2"] = self.wrong2_input.text().strip() or None
            data["wrong_answer_3"] = self.wrong3_input.text().strip() or None

        return data


class QuestionPool(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_add = QPushButton("+ New Question")
        self.btn_add.clicked.connect(self.add_question)
        self.btn_edit = QPushButton("Edit")
        self.btn_edit.clicked.connect(self.edit_question)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_question)
        self.btn_image = QPushButton("Upload Image")
        self.btn_image.clicked.connect(self.upload_image)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)

        # Filter by topic
        self.topic_filter = QComboBox()
        self.topic_filter.addItem("All Topics", None)
        self.topic_filter.currentIndexChanged.connect(self.refresh)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_image)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Filter:"))
        toolbar.addWidget(self.topic_filter)
        toolbar.addWidget(self.btn_refresh)
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Type", "Text", "Correct", "Topic", "Time", "Image"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_question)
        layout.addWidget(self.table)

    def refresh(self):
        # Refresh topic filter
        current_topic = self.topic_filter.currentData()
        self.topic_filter.blockSignals(True)
        self.topic_filter.clear()
        self.topic_filter.addItem("All Topics", None)
        try:
            topics = self.api.list_topics()
            for t in topics:
                self.topic_filter.addItem(f"{t['name']} ({t.get('question_count', 0)})", t["id"])
            if current_topic is not None:
                idx = self.topic_filter.findData(current_topic)
                if idx >= 0:
                    self.topic_filter.setCurrentIndex(idx)
        except Exception:
            pass
        self.topic_filter.blockSignals(False)

        topic_id = self.topic_filter.currentData()
        try:
            questions = self.api.list_questions(topic_id=topic_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load questions: {e}")
            return

        self.table.setRowCount(len(questions))
        for row, q in enumerate(questions):
            self.table.setItem(row, 0, QTableWidgetItem(str(q["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(q["question_type"]))
            text = (q.get("text") or "")[:80]
            self.table.setItem(row, 2, QTableWidgetItem(text))
            self.table.setItem(row, 3, QTableWidgetItem(q["correct_answer"]))
            self.table.setItem(row, 4, QTableWidgetItem(q.get("topic_name") or "-"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{q['time_seconds']}s"))
            self.table.setItem(row, 6, QTableWidgetItem("Yes" if q.get("image_filename") else ""))

    def _selected_question_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def add_question(self):
        dlg = QuestionDialog(self.api, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["correct_answer"]:
                QMessageBox.warning(self, "Error", "Correct answer is required.")
                return
            try:
                self.api.create_question(data)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create question: {e}")

    def edit_question(self):
        qid = self._selected_question_id()
        if qid is None:
            QMessageBox.information(self, "Info", "Select a question first.")
            return
        try:
            question = self.api.get_question(qid)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        dlg = QuestionDialog(self.api, self, question)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                self.api.update_question(qid, data)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update question: {e}")

    def delete_question(self):
        qid = self._selected_question_id()
        if qid is None:
            QMessageBox.information(self, "Info", "Select a question first.")
            return
        reply = QMessageBox.question(
            self, "Confirm", "Delete this question? It will be removed from all quizzes.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.api.delete_question(qid)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete question: {e}")

    def upload_image(self):
        qid = self._selected_question_id()
        if qid is None:
            QMessageBox.information(self, "Info", "Select a question first.")
            return
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp)",
        )
        if filepath:
            try:
                self.api.upload_image(qid, filepath)
                self.refresh()
                QMessageBox.information(self, "Success", "Image uploaded.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to upload image: {e}")
