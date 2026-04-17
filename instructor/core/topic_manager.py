from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLineEdit, QTextEdit, QLabel, QMessageBox,
    QHeaderView, QDialog, QDialogButtonBox, QFormLayout,
)
from PyQt6.QtCore import Qt

from instructor.api_client import ApiClient


class TopicDialog(QDialog):
    def __init__(self, parent=None, topic=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Topic" if topic else "New Topic")
        self.setMinimumWidth(400)

        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Topic name")
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Optional description")
        self.desc_input.setMaximumHeight(100)

        if topic:
            self.name_input.setText(topic.get("name", ""))
            self.desc_input.setText(topic.get("description", "") or "")

        layout.addRow("Name:", self.name_input)
        layout.addRow("Description:", self.desc_input)

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
        }


class TopicManager(QWidget):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_add = QPushButton("+ New Topic")
        self.btn_add.clicked.connect(self.add_topic)
        self.btn_edit = QPushButton("Edit")
        self.btn_edit.clicked.connect(self.edit_topic)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_topic)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_refresh)
        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Questions", "Description"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_topic)
        layout.addWidget(self.table)

    def refresh(self):
        try:
            topics = self.api.list_topics()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load topics: {e}")
            return

        self.table.setRowCount(len(topics))
        for row, t in enumerate(topics):
            self.table.setItem(row, 0, QTableWidgetItem(str(t["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(t["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(str(t.get("question_count", 0))))
            self.table.setItem(row, 3, QTableWidgetItem(t.get("description", "") or ""))

    def _selected_topic_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def add_topic(self):
        dlg = TopicDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if not data["name"]:
                QMessageBox.warning(self, "Error", "Name is required.")
                return
            try:
                self.api.create_topic(data["name"], data["description"])
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to create topic: {e}")

    def edit_topic(self):
        tid = self._selected_topic_id()
        if tid is None:
            QMessageBox.information(self, "Info", "Select a topic first.")
            return
        try:
            topic = self.api.get_topic(tid)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
            return

        dlg = TopicDialog(self, topic)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            try:
                self.api.update_topic(tid, **data)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update topic: {e}")

    def delete_topic(self):
        tid = self._selected_topic_id()
        if tid is None:
            QMessageBox.information(self, "Info", "Select a topic first.")
            return
        reply = QMessageBox.question(
            self, "Confirm", "Delete this topic?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.api.delete_topic(tid)
                self.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete topic: {e}")
