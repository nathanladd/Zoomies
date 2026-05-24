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

from instructor.api_client import ApiClient

import httpx


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


class ImageDropZone(QFrame):
    """Drag-and-drop / click-to-browse image picker. Emits fileSelected(path) and cleared()."""

    fileSelected = pyqtSignal(str)
    cleared = pyqtSignal()

    THUMB_MAX = 160

    def __init__(self, base_url: str = "http://localhost:5000", parent=None):
        super().__init__(parent)
        self._base_url = base_url
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
            r = httpx.get(f"{self._base_url}/media/questions/{filename}", timeout=5.0)
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
        self.image_zone = ImageDropZone(base_url=self.api.base_url)
        self._pending_image_path: str | None = None
        self._remove_image: bool = False
        self._existing_image: str | None = None
        self.image_zone.fileSelected.connect(self._on_image_selected)
        self.image_zone.cleared.connect(self._on_image_cleared)
        layout.addRow("Image:", self.image_zone)

        # Multiple-choice answers — four fixed A/B/C/D slots. Each row has a
        # radio button that marks which slot is the correct answer, plus a
        # free-text field for the answer text. Slots C and D are optional.
        # When the question's `randomize_answers` is disabled, the server shows
        # answers to students in this exact A/B/C/D order, which lets the
        # instructor write choices like "Both A and B" that reference the
        # letter labels directly.
        self.mc_letters = ["A", "B", "C", "D"]
        self.mc_group = QButtonGroup(self)
        self.mc_radios: dict[str, QRadioButton] = {}
        self.mc_inputs: dict[str, QLineEdit] = {}
        self.mc_stats: dict[str, QLabel] = {}
        mc_container = QWidget()
        mc_layout = QVBoxLayout(mc_container)
        mc_layout.setContentsMargins(0, 0, 0, 0)
        mc_layout.setSpacing(4)
        for letter in self.mc_letters:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            rb = QRadioButton(f"{letter}.")
            rb.setToolTip(f"Mark answer {letter} as the correct answer")
            le = QLineEdit()
            if letter in ("A", "B"):
                le.setPlaceholderText(f"Answer {letter}")
            else:
                le.setPlaceholderText(f"Answer {letter} (optional)")
            stat = QLabel("")
            stat.setMinimumWidth(70)
            stat.setStyleSheet("color: #555; font-size: 11px;")
            stat.setToolTip("Cumulative pick rate across all played sessions")
            self.mc_group.addButton(rb)
            self.mc_radios[letter] = rb
            self.mc_inputs[letter] = le
            self.mc_stats[letter] = stat
            row.addWidget(rb)
            row.addWidget(le, 1)
            row.addWidget(stat)
            row_widget = QWidget()
            row_widget.setLayout(row)
            mc_layout.addWidget(row_widget)
        self.mc_radios["A"].setChecked(True)
        layout.addRow("Answers:", mc_container)
        self._row_mc = layout.rowCount() - 1

        # True/False radio row — only shown when question_type == "true_false"
        self.tf_true = QRadioButton("True")
        self.tf_false = QRadioButton("False")
        self.tf_group = QButtonGroup(self)
        self.tf_group.addButton(self.tf_true)
        self.tf_group.addButton(self.tf_false)
        self.tf_true.setChecked(True)
        self.tf_stat_true = QLabel("")
        self.tf_stat_false = QLabel("")
        for s in (self.tf_stat_true, self.tf_stat_false):
            s.setStyleSheet("color: #555; font-size: 11px;")
            s.setMinimumWidth(70)
            s.setToolTip("Cumulative pick rate across all played sessions")
        tf_container = QWidget()
        tf_layout = QVBoxLayout(tf_container)
        tf_layout.setContentsMargins(0, 0, 0, 0)
        tf_layout.setSpacing(2)
        for rb, stat in ((self.tf_true, self.tf_stat_true), (self.tf_false, self.tf_stat_false)):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(rb)
            row.addStretch()
            row.addWidget(stat)
            rw = QWidget()
            rw.setLayout(row)
            tf_layout.addWidget(rw)
        layout.addRow("Answer:", tf_container)
        self._row_tf = layout.rowCount() - 1

        # Technician A/B radio rows — only shown when question_type == "technician_ab".
        # All four ASE choices are listed in fixed order; user picks the correct one.
        self.ab_choices = [
            ("A", "Technician A only"),
            ("B", "Technician B only"),
            ("C", "Both Technician A and Technician B"),
            ("D", "Neither Technician A nor Technician B"),
        ]
        self.ab_group = QButtonGroup(self)
        self.ab_radios: dict[str, QRadioButton] = {}
        self.ab_stats: dict[str, QLabel] = {}
        ab_container = QWidget()
        ab_layout = QVBoxLayout(ab_container)
        ab_layout.setContentsMargins(0, 0, 0, 0)
        ab_layout.setSpacing(2)
        for letter, text in self.ab_choices:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            rb = QRadioButton(f"{letter}. {text}")
            self.ab_group.addButton(rb)
            self.ab_radios[letter] = rb
            stat = QLabel("")
            stat.setStyleSheet("color: #555; font-size: 11px;")
            stat.setMinimumWidth(70)
            stat.setToolTip("Cumulative pick rate across all played sessions")
            self.ab_stats[letter] = stat
            row.addWidget(rb, 1)
            row.addWidget(stat)
            rw = QWidget()
            rw.setLayout(row)
            ab_layout.addWidget(rw)
        self.ab_radios["A"].setChecked(True)
        layout.addRow("Answers:", ab_container)
        self._row_ab = layout.rowCount() - 1

        # Cumulative answer-stats summary, sits below the answers so the
        # per-row pick-rate labels and the totals appear together. Populated
        # by `_load_stats` after the dialog finishes building; hidden entirely
        # when adding a new question.
        stats_row = QHBoxLayout()
        self.stats_summary = QLabel("")
        self.stats_summary.setStyleSheet("color: #555; font-size: 11px;")
        self.btn_reset_stats = QPushButton("Reset stats")
        self.btn_reset_stats.setVisible(False)
        self.btn_reset_stats.clicked.connect(self._reset_stats)
        stats_row.addWidget(self.stats_summary, 1)
        stats_row.addWidget(self.btn_reset_stats)
        stats_widget = QWidget()
        stats_widget.setLayout(stats_row)
        layout.addRow("Stats:", stats_widget)
        self._row_stats = layout.rowCount() - 1

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
            qtype = question.get("question_type", "multiple_choice")
            if qtype == "true_false":
                if ca.lower() == "false":
                    self.tf_false.setChecked(True)
                else:
                    self.tf_true.setChecked(True)
            if qtype == "multiple_choice":
                # Reconstruct the instructor's A/B/C/D layout. The server stores
                # [correct, wrong1, wrong2, wrong3] plus `correct_index` (0-3)
                # telling which slot the correct answer was in. Wrongs fill the
                # remaining slots in A/B/C/D order.
                wrongs = [
                    question.get("wrong_answer_1", "") or "",
                    question.get("wrong_answer_2", "") or "",
                    question.get("wrong_answer_3", "") or "",
                ]
                try:
                    correct_idx = int(question.get("correct_index") or 0)
                except (TypeError, ValueError):
                    correct_idx = 0
                correct_idx = max(0, min(correct_idx, 3))
                slots = [""] * 4
                slots[correct_idx] = ca
                wi = 0
                for i in range(4):
                    if i == correct_idx:
                        continue
                    slots[i] = wrongs[wi] if wi < len(wrongs) else ""
                    wi += 1
                for letter, value in zip(self.mc_letters, slots):
                    self.mc_inputs[letter].setText(value)
                self.mc_radios[self.mc_letters[correct_idx]].setChecked(True)
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
            if question.get("question_type") == "technician_ab":
                letter = (ca or "A").strip().upper()
                if letter not in self.ab_radios:
                    letter = "A"
                self.ab_radios[letter].setChecked(True)

        self._on_type_changed(self.type_combo.currentText())

        # Stats only make sense for existing questions. Hide the row otherwise
        # and load the cumulative tally for the current question.
        if question and question.get("id") is not None:
            self._load_stats()
        else:
            self._set_row_visible(self._row_stats, False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_randomize_user_toggle(self, _checked: bool):
        self._randomize_user_set = True

    def _apply_randomize_default(self, qtype: str):
        """Apply the per-type default for the randomize checkbox.

        technician_ab questions never randomize — the checkbox is forced off and
        disabled regardless of any prior user/saved value. For other types, the
        default is only applied when the user hasn't explicitly toggled it.
        """
        if qtype in ("technician_ab", "true_false"):
            self.randomize_check.blockSignals(True)
            self.randomize_check.setChecked(False)
            self.randomize_check.blockSignals(False)
            self.randomize_check.setEnabled(False)
            return
        self.randomize_check.setEnabled(True)
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
        is_ab = qtype == "technician_ab"
        is_mc = qtype == "multiple_choice"

        # Each answer-entry row only shows for its own type.
        self._set_row_visible(self._row_tf, is_tf)
        self._set_row_visible(self._row_ab, is_ab)
        self._set_row_visible(self._row_mc, is_mc)

    def get_data(self) -> dict:
        qtype = self.type_combo.currentText()
        topic_id = self.topic_combo.currentData()

        data = {
            "question_type": qtype,
            "topic_id": topic_id,
            "text": self.text_input.toPlainText().strip() or None,
            "correct_answer": "",
            "wrong_answer_1": "",
            "wrong_answer_2": None,
            "wrong_answer_3": None,
            "time_seconds": self.time_slider.value(),
            "randomize_answers": self.randomize_check.isChecked(),
        }

        if qtype == "true_false":
            chosen = "True" if self.tf_true.isChecked() else "False"
            data["correct_answer"] = chosen
            data["wrong_answer_1"] = "False" if chosen == "True" else "True"
            data["wrong_answer_2"] = None
            data["wrong_answer_3"] = None
        elif qtype == "multiple_choice":
            # Collect A/B/C/D answer texts, determine which slot is correct,
            # and send correct_answer + wrong_answer_1..3 in A/B/C/D order
            # (skipping the correct slot). When randomize_answers is False,
            # the server displays them in the exact order we send the wrongs,
            # so letter-referencing choices like "Both A and B" stay stable.
            correct_letter = "A"
            for letter in self.mc_letters:
                if self.mc_radios[letter].isChecked():
                    correct_letter = letter
                    break
            values = {
                letter: self.mc_inputs[letter].text().strip()
                for letter in self.mc_letters
            }
            data["correct_answer"] = values[correct_letter]
            data["correct_index"] = self.mc_letters.index(correct_letter)
            wrongs = [
                values[letter]
                for letter in self.mc_letters
                if letter != correct_letter
            ]
            data["wrong_answer_1"] = wrongs[0] if len(wrongs) > 0 else ""
            data["wrong_answer_2"] = wrongs[1] if len(wrongs) > 1 and wrongs[1] else None
            data["wrong_answer_3"] = wrongs[2] if len(wrongs) > 2 and wrongs[2] else None
        elif qtype == "technician_ab":
            # Technician A/B answers are fixed and never randomized; the user
            # picked the correct letter via the radio group.
            letters = [letter for letter, _ in self.ab_choices]
            correct_letter = "A"
            for letter in letters:
                if self.ab_radios[letter].isChecked():
                    correct_letter = letter
                    break
            choices = [text for _, text in self.ab_choices]
            idx = letters.index(correct_letter)
            data["correct_answer"] = correct_letter
            data["randomize_answers"] = False
            wrong = [c for i, c in enumerate(choices) if i != idx]
            data["wrong_answer_1"] = wrong[0] if len(wrong) > 0 else ""
            data["wrong_answer_2"] = wrong[1] if len(wrong) > 1 else None
            data["wrong_answer_3"] = wrong[2] if len(wrong) > 2 else None

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

    # ── Cumulative answer stats ────────────────────────────────────────
    def _load_stats(self):
        """Fetch cumulative pick rates for this question and refresh labels."""
        if not self.question:
            return
        qid = self.question.get("id")
        if qid is None:
            return
        try:
            stats = self.api.get_question_stats(int(qid))
        except Exception as e:
            self.stats_summary.setText(f"(stats unavailable: {e})")
            self.btn_reset_stats.setVisible(False)
            return
        self._stats_cache = stats
        total = int(stats.get("total", 0) or 0)
        non_responses = int(stats.get("non_responses", 0) or 0)
        non_pct = float(stats.get("non_response_percentage", 0.0) or 0.0)
        if total == 0:
            self.stats_summary.setText("No answers recorded yet.")
        else:
            self.stats_summary.setText(
                f"Total: {total}  ·  no response: {non_responses} ({non_pct:.0f}%)"
            )
        self.btn_reset_stats.setVisible(total > 0)
        self._apply_stats(stats)

    def _format_pct(self, pct: float, count: int) -> str:
        return f"{pct:.0f}% ({count})"

    # Base font size kept in sync with the widget styling in __init__.
    _STAT_BASE_STYLE = "font-size: 11px;"
    _STAT_STYLE_NEUTRAL = f"color: #555; {_STAT_BASE_STYLE}"
    _STAT_STYLE_CORRECT = f"color: #15803d; font-weight: bold; {_STAT_BASE_STYLE}"
    _STAT_STYLE_WRONG = f"color: #b91c1c; font-weight: bold; {_STAT_BASE_STYLE}"

    def _style_stat_label(self, label: QLabel, is_correct: bool, has_text: bool) -> None:
        """Color the stat green if it belongs to the correct answer, red if
        it belongs to a wrong answer. Empty slots stay neutral gray."""
        if not has_text:
            label.setStyleSheet(self._STAT_STYLE_NEUTRAL)
        elif is_correct:
            label.setStyleSheet(self._STAT_STYLE_CORRECT)
        else:
            label.setStyleSheet(self._STAT_STYLE_WRONG)

    def _apply_stats(self, stats: dict):
        counts = stats.get("counts", {}) or {}
        percentages = stats.get("percentages", {}) or {}

        def lookup(text: str) -> str:
            text = (text or "").strip()
            if not text:
                return ""
            count = int(counts.get(text, 0) or 0)
            pct = float(percentages.get(text, 0.0) or 0.0)
            return self._format_pct(pct, count)

        # Multiple-choice: each slot has free-form text we can match directly.
        # The radio that's currently checked marks the correct answer.
        for letter, le in self.mc_inputs.items():
            txt = lookup(le.text())
            lbl = self.mc_stats[letter]
            lbl.setText(txt)
            is_correct = self.mc_radios[letter].isChecked() and bool(le.text().strip())
            self._style_stat_label(lbl, is_correct, bool(txt))

        # True/False: stored under literal strings "True" / "False".
        tf_true_txt = lookup("True")
        tf_false_txt = lookup("False")
        self.tf_stat_true.setText(tf_true_txt)
        self.tf_stat_false.setText(tf_false_txt)
        self._style_stat_label(self.tf_stat_true, self.tf_true.isChecked(), bool(tf_true_txt))
        self._style_stat_label(self.tf_stat_false, self.tf_false.isChecked(), bool(tf_false_txt))

        # Technician A/B: stored under the full phrase (label prefix stripped).
        for letter, phrase in self.ab_choices:
            txt = lookup(phrase)
            lbl = self.ab_stats[letter]
            lbl.setText(txt)
            self._style_stat_label(lbl, self.ab_radios[letter].isChecked(), bool(txt))

    def _reset_stats(self):
        if not self.question:
            return
        qid = self.question.get("id")
        if qid is None:
            return
        confirm = QMessageBox.question(
            self, "Reset stats",
            "Clear the cumulative answer-pick tally for this question?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.reset_question_stats(int(qid))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to reset stats: {e}")
            return
        self._load_stats()


class QuestionPool(QWidget):
    # Emitted when the instructor clicks the "Topics…" toolbar button so
    # MainWindow can open the Settings dialog on the Topics tab.
    topics_requested = pyqtSignal()

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
        self.btn_topics = QPushButton("Topics…")
        self.btn_topics.setToolTip("Manage topics in Settings")
        self.btn_topics.clicked.connect(self.topics_requested)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)

        # Sort selector — applied client-side after fetching the question list.
        # "Most missed" pulls aggregate miss-rate stats and orders questions
        # with the highest miss rate first; ties / zero-data fall back to
        # newest-first so the list stays stable for fresh installs.
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Newest", "newest")
        self.sort_combo.addItem("Oldest", "oldest")
        self.sort_combo.addItem("Most missed", "most_missed")
        self.sort_combo.currentIndexChanged.connect(self.refresh)

        # Filter by question type — kept separate from the topic filter so the
        # two can be combined (e.g. only multiple-choice within a given topic).
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", None)
        self.type_filter.addItem("Multiple choice", "multiple_choice")
        self.type_filter.addItem("True/False", "true_false")
        self.type_filter.addItem("Tech A/B", "technician_ab")
        self.type_filter.currentIndexChanged.connect(self.refresh)

        # Filter by topic
        self.topic_filter = QComboBox()
        self.topic_filter.addItem("All Topics", None)
        self.topic_filter.currentIndexChanged.connect(self.refresh)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
        toolbar.addWidget(self.btn_topics)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Sort:"))
        toolbar.addWidget(self.sort_combo)
        toolbar.addWidget(QLabel("Filter:"))
        toolbar.addWidget(self.type_filter)
        toolbar.addWidget(self.topic_filter)
        toolbar.addWidget(self.btn_refresh)
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Type", "Text", "Correct", "Topic", "Time", "Image"])
        _hdr = self.table.horizontalHeader()
        for _i in range(7):
            _hdr.setSectionResizeMode(_i, QHeaderView.ResizeMode.Interactive)
        _hdr.setStretchLastSection(False)
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

        type_filter = self.type_filter.currentData() if hasattr(self, "type_filter") else None
        if type_filter:
            questions = [q for q in questions if q.get("question_type") == type_filter]

        sort_mode = self.sort_combo.currentData() if hasattr(self, "sort_combo") else "newest"
        if sort_mode == "oldest":
            questions.sort(key=lambda q: int(q["id"]))
        elif sort_mode == "most_missed":
            try:
                summary = self.api.list_question_stats_summary()
                miss_by_id = {
                    int(s["question_id"]): (
                        float(s.get("miss_rate", 0.0) or 0.0),
                        int(s.get("miss_count", 0) or 0),
                    )
                    for s in summary
                }
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load stats: {e}")
                miss_by_id = {}
            # Highest miss-rate first, then highest miss-count, then newest id.
            questions.sort(
                key=lambda q: (
                    -miss_by_id.get(int(q["id"]), (0.0, 0))[0],
                    -miss_by_id.get(int(q["id"]), (0.0, 0))[1],
                    -int(q["id"]),
                )
            )

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
        self.table.resizeColumnsToContents()

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

    def edit_question_by_id(self, qid: int):
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

    def edit_question(self):
        qid = self._selected_question_id()
        if qid is None:
            QMessageBox.information(self, "Info", "Select a question first.")
            return
        self.edit_question_by_id(qid)

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
