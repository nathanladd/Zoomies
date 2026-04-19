import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QVBoxLayout,
    QStatusBar, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QProcess
from PyQt6.QtGui import QAction

from instructor.api_client import ApiClient
from instructor.core.topic_manager import TopicManager
from instructor.core.question_pool import QuestionPool
from instructor.core.quiz_builder import QuizBuilder
from instructor.game.control_panel import GameControlPanel, kill_port_processes
from version import __version__

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Name must match AppMutex in installer/Zundpunkt.iss so Inno Setup can detect
# a running instance during install/uninstall and offer to close it.
SINGLETON_MUTEX_NAME = "ZundpunktSingletonMutex"
_SINGLETON_MUTEX_HANDLE = None


def _acquire_singleton_mutex() -> None:
    """Create a Windows named mutex the installer can poll.

    The handle is stashed on a module global so Python doesn't GC it — the OS
    releases the mutex automatically when the process exits. Never blocks or
    refuses startup; a pre-existing mutex just means the installer will see
    "Zündpunkt is running" and prompt the user.
    """
    global _SINGLETON_MUTEX_HANDLE
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        CreateMutexW = ctypes.windll.kernel32.CreateMutexW
        CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        CreateMutexW.restype = wintypes.HANDLE
        _SINGLETON_MUTEX_HANDLE = CreateMutexW(None, False, SINGLETON_MUTEX_NAME)
    except Exception:
        # Non-fatal: losing the mutex just means the installer can't auto-close us.
        _SINGLETON_MUTEX_HANDLE = None


def _wait_for_server(host: str, port: int, timeout_s: float = 15.0) -> bool:
    """Poll the server's /api/topics endpoint until it responds 2xx or we time out."""
    deadline = time.monotonic() + timeout_s
    url = f"http://{host}:{port}/api/topics"
    while time.monotonic() < deadline:
        try:
            r = httpx.get(url, timeout=1.0)
            if r.status_code < 500:
                return True
        except Exception:
            pass
        time.sleep(0.25)
    return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Zündpunkt v{__version__}")
        self.setMinimumSize(1000, 700)

        # Start the backend server BEFORE building tabs (they hit the API on init).
        self.server_process: QProcess | None = None
        self._start_server()
        if not _wait_for_server(SERVER_HOST, SERVER_PORT, timeout_s=15.0):
            QMessageBox.critical(
                self, "Server did not start",
                f"The Zündpunkt server did not come online on port {SERVER_PORT} within 15 seconds.\n\n"
                "Check the Server Console on the Game tab for errors, then restart the instructor app.",
            )

        self.api = ApiClient()

        self._build_ui()
        self._build_menu()
        self.statusBar().showMessage(f"Connected to server at {SERVER_HOST}:{SERVER_PORT}")

    # ── Server lifecycle ──────────────────────────────────────────────────

    def _start_server(self):
        kill_port_processes(SERVER_PORT)  # clean up zombies from any previous run
        self.server_process = QProcess(self)
        self.server_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        if getattr(sys, "frozen", False):
            # In a frozen build the installer ships a sibling Zundpunkt-Server.exe
            # (console subsystem) next to Zundpunkt.exe — see the PyInstaller spec.
            install_dir = Path(sys.executable).parent
            server_exe = install_dir / "Zundpunkt-Server.exe"
            self.server_process.setWorkingDirectory(str(install_dir))
            self.server_process.start(str(server_exe), [])
        else:
            self.server_process.setWorkingDirectory(str(PROJECT_ROOT))
            self.server_process.start(sys.executable, ["run_server.py"])
        self.server_process.waitForStarted(3000)

    def _stop_server(self):
        if not self.server_process:
            return
        if self.server_process.state() != QProcess.ProcessState.NotRunning:
            pid = self.server_process.processId()
            if pid:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
                )
            self.server_process.waitForFinished(2000)
        kill_port_processes(SERVER_PORT)

    def _build_ui(self):
        # Tabs for content management
        self.topic_mgr = TopicManager(self.api)
        self.question_pool = QuestionPool(self.api)
        self.quiz_builder = QuizBuilder(self.api)

        # Game panel is the main window's central widget
        self.game_panel = GameControlPanel(self.api, server_process=self.server_process)
        self.setCentralWidget(self.game_panel)

        # Dock widgets for authoring tools
        self.dock_topics = self._make_dock("Topics", self.topic_mgr)
        self.dock_questions = self._make_dock("Questions", self.question_pool)
        self.dock_quizzes = self._make_dock("Quiz Builder", self.quiz_builder)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_topics)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_questions)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_quizzes)
        # Stack them as tabs in the same dock area to save space
        self.tabifyDockWidget(self.dock_topics, self.dock_questions)
        self.tabifyDockWidget(self.dock_questions, self.dock_quizzes)
        self.dock_topics.raise_()

        # Start with all authoring docks hidden so the Game panel has full space;
        # the View menu lets the instructor show them on demand.
        for dock in (self.dock_topics, self.dock_questions, self.dock_quizzes):
            dock.hide()

        status = QStatusBar()
        self.setStatusBar(status)

    def _make_dock(self, title: str, widget: QWidget) -> QDockWidget:
        dock = QDockWidget(title, self)
        dock.setObjectName(f"dock_{title.lower().replace(' ', '_')}")
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable,
        )
        dock.setWidget(widget)
        return dock

    def _build_menu(self):
        menubar = self.menuBar()

        # File menu — game lifecycle + app exit
        file_menu = menubar.addMenu("&File")

        new_game_action = QAction("&New Game", self)
        new_game_action.setShortcut("Ctrl+N")
        new_game_action.triggered.connect(self.game_panel._create_game)
        file_menu.addAction(new_game_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu — dock visibility toggles
        view_menu = menubar.addMenu("&View")
        for dock in (self.dock_topics, self.dock_questions, self.dock_quizzes):
            action = dock.toggleViewAction()  # checkable, auto-synced with the dock
            view_menu.addAction(action)

        # Database menu
        db_menu = menubar.addMenu("&Database")

        backup_action = QAction("&Backup Database…", self)
        backup_action.triggered.connect(self._backup_database)
        db_menu.addAction(backup_action)

        restore_action = QAction("&Restore Database…", self)
        restore_action.triggered.connect(self._restore_database)
        db_menu.addAction(restore_action)

    def _backup_database(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        default = str(Path.home() / f"zundpunkt-{stamp}.zip")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Backup As", default, "Zip archives (*.zip)",
        )
        if not path:
            return
        try:
            result = self.api.backup_database(path)
        except Exception as e:
            QMessageBox.warning(self, "Backup failed", str(e))
            return
        size_kb = result["size_bytes"] / 1024
        QMessageBox.information(
            self, "Backup complete",
            f"Saved to:\n{result['path']}\n\n{size_kb:,.1f} KB",
        )

    def _restore_database(self):
        confirm = QMessageBox.warning(
            self, "Restore Database",
            "This will replace the current database and question images with the contents of the backup.\n\n"
            "Your current data will be moved to data/pre-restore-<timestamp>/.\n\n"
            "The server must be restarted after restoring. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup Zip", str(Path.home()), "Zip archives (*.zip)",
        )
        if not path:
            return
        try:
            result = self.api.restore_database(path)
        except Exception as e:
            QMessageBox.warning(self, "Restore failed", str(e))
            return
        QMessageBox.information(
            self, "Restore complete",
            f"Restored from:\n{result.get('restored_from', path)}\n\n"
            f"Previous state: {result.get('previous_state', '?')}\n\n"
            f"{result.get('notice', '')}",
        )

    def closeEvent(self, event):
        # ProjectionWindow is a parentless top-level window, so closing the
        # main window doesn't cascade to it. Close it explicitly.
        proj = getattr(self.game_panel, "projection_window", None)
        if proj is not None:
            proj.close()
            self.game_panel.projection_window = None
        # Tear down the WS thread the game panel owns before the server dies.
        if getattr(self.game_panel, "ws_thread", None) is not None:
            try:
                self.game_panel.ws_thread.stop()
                self.game_panel.ws_thread.wait(1000)
            except Exception:
                pass
        self.api.close()
        self._stop_server()
        event.accept()


def main():
    # Claim the named mutex before anything heavy so a parallel installer run
    # can see "Zündpunkt is running" as soon as possible.
    _acquire_singleton_mutex()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 40))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 230))
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 35))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 50))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(40, 40, 55))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 230))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 230))
    palette.setColor(QPalette.ColorRole.Button, QColor(40, 40, 55))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 230))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 100, 100))
    palette.setColor(QPalette.ColorRole.Link, QColor(99, 102, 241))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(99, 102, 241))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
