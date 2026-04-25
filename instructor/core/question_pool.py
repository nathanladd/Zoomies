import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QTextEdit, QLabel, QMessageBox,
    QHeaderView, QDialog, QDialogButtonBox, QFormLayout, QComboBox,
    QSlider, QFileDialog, QGroupBox, QFrame, QCheckBox, QRadioButton,
    QButtonGroup,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap

from instructor.api_client import ApiClient, BASE_URL

import httpx


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class ImageDropZone(QFrame):
    """Drag-and-drop / click-to-browse image picker. Emits fileSelected(path) and cleared()."""

    fileSelected = pyqtSignal(str)
    cleared = pyqtSignal()

    THUMB_MAX = 160

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(70)
        self.setStyleSheet(
            "ImageDropZone { border: 2px dashed #888; border-radius: 6px; background: #fafafa; }"
            "ImageDropZone[dragOver=\"true\"] { border-color: #2a7; background: #eef9f0; }"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        top = QHBoxLayout()
        self.label = QLabel("Drop image here or click Browse…")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.clicked.connect(self._browse)
        self.btn_clear = QPushButton("Remove")
        self.btn_clear.clicked.connect(self._clear)
        self.btn_clear.setVisible(False)
        top.addWidget(self.label, 1)
        top.addWidget(self.btn_browse)
        top.addWidget(self.btn_clear)
        outer.addLayout(top)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(self.THUMB_MAX)
        self.preview.setVisible(False)
        outer.addWidget(self.preview)

    def set_existing(self, filename: str | None):
        if filename:
            self.label.setText(f"Current: {filename}")
            self.btn_clear.setVisible(True)
            self._load_remote_preview(filename)
        else:
            self.label.setText("Drop image here or click Browse…")
            self.btn_clear.setVisible(False)
            self._set_preview_pixmap(None)

    def _set_preview_pixmap(self, pix: QPixmap | None):
        if pix is None or pix.isNull():
            self.preview.clear()
            self.preview.setVisible(False)
            return
        scaled = pix.scaled(
            self.THUMB_MAX, self.THUMB_MAX,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setPixmap(scaled)
        self.preview.setVisible(True)

    def _load_local_preview(self, path: str):
        pix = QPixmap(path)
        self._set_preview_pixmap(pix if not pix.isNull() else None)

    def _load_remote_preview(self, filename: str):
        try:
            r = httpx.get(f"{BASE_URL}/media/questions/{filename}", timeout=5.0)
            if r.status_code == 200:
                pix = QPixmap()
                pix.loadFromData(r.content)
                self._set_preview_pixmap(pix if not pix.isNull() else None)
                return
        except Exception:
            pass
        self._set_preview_pixmap(None)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp)",
        )
        if path:
            self._accept_path(path)

    def _clear(self):
        self.label.setText("Drop image here or click Browse…")
        self.btn_clear.setVisible(False)
        self._set_preview_pixmap(None)
        self.cleared.emit()

    def _accept_path(self, path: str):
        ext = os.path.splitext(path)[1].lower()
        if ext not in IMAGE_EXTS:
            QMessageBox.warning(self, "Invalid", f"Unsupported image type: {ext}")
            return
        self.label.setText(f"Selected: {os.path.basename(path)}")
        self.btn_clear.setVisible(True)
        self._load_local_preview(path)
        self.fileSelected.emit(path)

    # ── Drag & drop ────────────────────────────────────────────────────
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls() and any(
            u.isLocalFile() and os.path.splitext(u.toLocalFile())[1].lower() in IMAGE_EXTS
            for u in e.mimeData().urls()
        ):
            self.setProperty("dragOver", "true")
            self.style().unpolish(self); self.style().polish(self)
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self.setProperty("dragOver", "false")
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, e: QDropEvent):
        self.setProperty("dragOver", "false")
        self.style().unpolish(self); self.style().polish(self)
        for u in e.mimeData().urls():
            if u.isLocalFile():
                p = u.toLocalFile()
                if os.path.splitext(p)[1].lower() in IMAGE_EXTS:
                    self._accept_path(p)
                    e.acceptProposedAction()
                    return
        e.ignore()


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

        # Image (drag-and-drop) — sits between question text and answers
        self.image_zone = ImageDropZone()
        self._pending_image_path: str | None = None
        self._remove_image: bool = False
        self._existing_image: str | None = None
        self.image_zone.fileSelected.connect(self._on_image_selected)
        self.image_zone.cleared.connect(self._on_image_cleared)
        layout.addRow("Image:", self.image_zone)

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
        self._row_correct = layout.rowCount() - 1
        layout.addRow("Wrong 1:", self.wrong1_input)
        self._row_wrong1 = layout.rowCount() - 1
        layout.addRow("Wrong 2:", self.wrong2_input)
        self._row_wrong2 = layout.rowCount() - 1
        layout.addRow("Wrong 3:", self.wrong3_input)
        self._row_wrong3 = layout.rowCount() - 1

        # True/False radio row — only shown when question_type == "true_false"
        tf_row = QHBoxLayout()
        self.tf_true = QRadioButton("True")
        self.tf_false = QRadioButton("False")
        self.tf_group = QButtonGroup(self)
        self.tf_group.addButton(self.tf_true)
        self.tf_group.addButton(self.tf_false)
        self.tf_true.setChecked(True)
        tf_row.addWidget(self.tf_true)
        tf_row.addWidget(self.tf_false)
        tf_row.addStretch()
        tf_widget = QWidget()
        tf_widget.setLayout(tf_row)
        layout.addRow("Answer:", tf_widget)
        self._row_tf = layout.rowCount() - 1
        self._form_layout = layout

        # Time slider
        time_row = QHBoxLayout()
        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setRange(5, 30)
        self.time_slider.setValue(20)
        self.time_slider.setTickInterval(5)
        self.time_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.time_label = QLabel("20s")
        self.time_slider.valueChanged.connect(lambda v: self.time_label.setText(f"{v}s"))
        time_row.addWidget(self.time_slider)
        time_row.addWidget(self.time_label)
        layout.addRow("Time:", time_row)

        # Randomize answers checkbox
        self.randomize_check = QCheckBox("Randomize answer order")
        self._randomize_user_set = False
        self.randomize_check.toggled.connect(self._on_randomize_user_toggle)
        layout.addRow("", self.randomize_check)

        # Populate if editing
        if question:
            self.type_combo.setCurrentText(question.get("question_type", "multiple_choice"))
            tid = question.get("topic_id")
            if tid:
                idx = self.topic_combo.findData(tid)
                if idx >= 0:
                    self.topic_combo.setCurrentIndex(idx)
            self.text_input.setText(question.get("text", "") or "")
            ca = question.get("correct_answer", "") or ""
            self.correct_input.setText(ca)
            if (question.get("question_type") == "true_false"):
                if ca.lower() == "false":
                    self.tf_false.setChecked(True)
                else:
                    self.tf_true.setChecked(True)
            self.wrong1_input.setText(question.get("wrong_answer_1", ""))
            self.wrong2_input.setText(question.get("wrong_answer_2", "") or "")
            self.wrong3_input.setText(question.get("wrong_answer_3", "") or "")
            self.time_slider.setValue(question.get("time_seconds", 10))
            self._existing_image = question.get("image_filename")
            self.image_zone.set_existing(self._existing_image)
            ra = question.get("randomize_answers")
            if ra is not None:
                # Mark as user-set so type changes don't overwrite the saved value.
                self.randomize_check.blockSignals(True)
                self.randomize_check.setChecked(bool(ra))
                self.randomize_check.blockSignals(False)
                self._randomize_user_set = True

        self._on_type_changed(self.type_combo.currentText())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_randomize_user_toggle(self, _checked: bool):
        self._randomize_user_set = True

    def _apply_randomize_default(self, qtype: str):
        """If the user hasn't explicitly set the checkbox, apply the per-type default."""
        if self._randomize_user_set:
            return
        default = qtype == "multiple_choice"
        self.randomize_check.blockSignals(True)
        self.randomize_check.setChecked(default)
        self.randomize_check.blockSignals(False)

    def _set_row_visible(self, row: int, visible: bool):
        # Qt 6.4+ has QFormLayout.setRowVisible; fall back to toggling widgets.
        try:
            self._form_layout.setRowVisible(row, visible)
            return
        except AttributeError:
            pass
        item_label = self._form_layout.itemAt(row, QFormLayout.ItemRole.LabelRole)
        item_field = self._form_layout.itemAt(row, QFormLayout.ItemRole.FieldRole)
        for item in (item_label, item_field):
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.setVisible(visible)

    def _on_type_changed(self, qtype: str):
        self._apply_randomize_default(qtype)
        is_tf = qtype == "true_false"

        # True/False row only shows for true_false; all text answer rows hide.
        self._set_row_visible(self._row_tf, is_tf)
        for row in (self._row_correct, self._row_wrong1,
                    self._row_wrong2, self._row_wrong3):
            self._set_row_visible(row, not is_tf)

        if qtype == "technician_ab":
            self.correct_input.setEnabled(True)
            self.correct_input.setPlaceholderText("A, B, C, or D")
            self.wrong1_input.setText("(auto)")
            self.wrong1_input.setEnabled(False)
            self.wrong2_input.clear()
            self.wrong2_input.setEnabled(False)
            self.wrong3_input.clear()
            self.wrong3_input.setEnabled(False)
        elif not is_tf:
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
            "randomize_answers": self.randomize_check.isChecked(),
        }

        if qtype == "true_false":
            chosen = "True" if self.tf_true.isChecked() else "False"
            data["correct_answer"] = chosen
            data["wrong_answer_1"] = "False" if chosen == "True" else "True"
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

    def _on_image_selected(self, path: str):
        self._pending_image_path = path
        self._remove_image = False

    def _on_image_cleared(self):
        self._pending_image_path = None
        # Only flag removal if there was an existing server-side image.
        self._remove_image = bool(self._existing_image)

    def pending_image_path(self) -> str | None:
        return self._pending_image_path

    def should_remove_image(self) -> bool:
        return self._remove_image


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
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)

        # Filter by topic
        self.topic_filter = QComboBox()
        self.topic_filter.addItem("All Topics", None)
        self.topic_filter.currentIndexChanged.connect(self.refresh)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
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
            self.table.setItem(row, 6, QTableWidgetItem(q.get("image_filename") or ""))

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
                created = self.api.create_question(data)
                img = dlg.pending_image_path()
                if img:
                    try:
                        self.api.upload_image(created["id"], img)
                    except Exception as e:
                        QMessageBox.warning(self, "Image Upload Failed", str(e))
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
                img = dlg.pending_image_path()
                if img:
                    try:
                        self.api.upload_image(qid, img)
                    except Exception as e:
                        QMessageBox.warning(self, "Image Upload Failed", str(e))
                elif dlg.should_remove_image():
                    try:
                        self.api.delete_image(qid)
                    except Exception as e:
                        QMessageBox.warning(self, "Image Remove Failed", str(e))
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
