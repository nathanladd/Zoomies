"""Update-available dialog: shows release notes + Update Now / Later / Skip buttons.

When "Update Now" is clicked the dialog switches to an inline download progress
view, verifies SHA-256, launches the installer, then quits the app.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile

import httpx
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox,
    QProgressBar, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from version import __version__


class _DownloadThread(QThread):
    progress = pyqtSignal(int, int)  # bytes_downloaded, total_bytes
    finished = pyqtSignal(str)       # dest path, or "" if cancelled
    error = pyqtSignal(str)

    def __init__(self, url: str, dest: str):
        super().__init__()
        self.url = url
        self.dest = dest
        self._cancel = False

    def run(self) -> None:
        try:
            with httpx.stream("GET", self.url, timeout=None, follow_redirects=True) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(self.dest, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=65536):
                        if self._cancel:
                            self.finished.emit("")
                            return
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total)
            self.finished.emit(self.dest)
        except Exception as exc:
            self.error.emit(str(exc))

    def cancel(self) -> None:
        self._cancel = True


class UpdateDialog(QDialog):
    """Shown when the UpdateChecker finds a newer version."""

    def __init__(
        self,
        latest_version: str,
        notes: str,
        download_url: str,
        sha256: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.setMinimumWidth(520)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        self.latest_version = latest_version
        self.notes = notes
        self.download_url = download_url
        self.sha256 = sha256.lower() if sha256 else ""
        self._thread: _DownloadThread | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)

        header = QLabel(
            f"<b>Rudi {self.latest_version} is available</b>"
            f"  <span style='color:#888;font-weight:normal;'>(you have v{__version__})</span>"
        )
        header.setStyleSheet("font-size: 14px;")
        root.addWidget(header)

        if self.notes:
            notes_label = QLabel("What's new:")
            notes_label.setStyleSheet("font-weight: bold; margin-top: 4px;")
            root.addWidget(notes_label)
            notes_box = QTextEdit()
            notes_box.setReadOnly(True)
            notes_box.setPlainText(self.notes)
            notes_box.setMaximumHeight(130)
            notes_box.setStyleSheet("font-size: 12px; background: #F8F8F8; border: 1px solid #D0D0D0;")
            root.addWidget(notes_box)

        # Progress area — hidden until download starts
        self._progress_widget = QWidget()
        prog_layout = QVBoxLayout(self._progress_widget)
        prog_layout.setContentsMargins(0, 0, 0, 0)
        self._status_label = QLabel("Downloading…")
        prog_layout.addWidget(self._status_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        prog_layout.addWidget(self._progress_bar)
        self._progress_widget.hide()
        root.addWidget(self._progress_widget)

        # Action buttons (the main "choice" row)
        self._btn_widget = QWidget()
        btn_row = QHBoxLayout(self._btn_widget)
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.addStretch()

        self._btn_skip = QPushButton("Skip This Version")
        self._btn_later = QPushButton("Remind Me Later")
        self._btn_update = QPushButton("Update Now")
        self._btn_update.setStyleSheet(
            "QPushButton { background-color: #0078D4; color: white; font-weight: bold; "
            "padding: 4px 18px; border-radius: 4px; } "
            "QPushButton:hover { background-color: #005a9e; } "
            "QPushButton:pressed { background-color: #004880; }"
        )
        self._btn_skip.clicked.connect(self._on_skip)
        self._btn_later.clicked.connect(self._on_later)
        self._btn_update.clicked.connect(self._on_update_now)

        btn_row.addWidget(self._btn_skip)
        btn_row.addWidget(self._btn_later)
        btn_row.addWidget(self._btn_update)
        root.addWidget(self._btn_widget)

        # Cancel button (shown only while downloading)
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self._on_cancel)
        self._btn_cancel.hide()
        root.addWidget(self._btn_cancel)

    # ── button handlers ───────────────────────────────────────────────────────

    def _on_skip(self) -> None:
        from instructor.app_settings import save as save_settings
        save_settings(skipped_version=self.latest_version)
        self.reject()

    def _on_later(self) -> None:
        self.reject()

    def _on_update_now(self) -> None:
        self._btn_widget.hide()
        self._progress_widget.show()
        self._btn_cancel.show()
        self.adjustSize()

        filename = self.download_url.split("/")[-1] or f"Rudi-Setup-{self.latest_version}.exe"
        dest = os.path.join(tempfile.gettempdir(), filename)

        self._thread = _DownloadThread(self.download_url, dest)
        self._thread.progress.connect(self._on_progress)
        self._thread.finished.connect(self._on_download_finished)
        self._thread.error.connect(self._on_download_error)
        self._thread.start()

    def _on_cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(3000)
        self._restore_buttons()

    # ── download progress ─────────────────────────────────────────────────────

    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int(downloaded * 100 / total)
            self._progress_bar.setValue(pct)
            mb_done = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self._status_label.setText(f"Downloading… {mb_done:.1f} / {mb_total:.1f} MB")
        else:
            self._status_label.setText(f"Downloading… {downloaded // 1024} KB")

    def _on_download_finished(self, path: str) -> None:
        if not path:
            self._restore_buttons()
            return

        self._status_label.setText("Verifying…")
        self._progress_bar.setValue(100)

        if self.sha256:
            try:
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(65536), b""):
                        h.update(chunk)
                if h.hexdigest().lower() != self.sha256:
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
                    QMessageBox.critical(
                        self,
                        "Integrity Check Failed",
                        "The downloaded file did not match the expected checksum.\n"
                        "The file has been removed. Please try again.",
                    )
                    self._restore_buttons()
                    return
            except Exception as exc:
                QMessageBox.critical(self, "Verification Error", f"Could not verify download:\n{exc}")
                self._restore_buttons()
                return

        self._status_label.setText("Launching installer…")
        try:
            subprocess.Popen([path], shell=False)
        except Exception as exc:
            QMessageBox.critical(self, "Launch Failed", f"Could not start the installer:\n{exc}")
            self._restore_buttons()
            return

        QApplication.instance().quit()

    def _on_download_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Download Failed", f"Could not download the update:\n{msg}")
        self._restore_buttons()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _restore_buttons(self) -> None:
        self._progress_widget.hide()
        self._btn_cancel.hide()
        self._btn_widget.show()
        self.adjustSize()

    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(3000)
        event.accept()
