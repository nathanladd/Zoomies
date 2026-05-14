import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QWidget, QStatusBar,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction

from instructor.api_client import ApiClient
from instructor.core.question_pool import QuestionPool
from instructor.core.quiz_builder import QuizBuilder
from instructor.game.control_panel import GameControlPanel
from instructor.ui.scoring_window import SettingsWindow
from version import __version__

# Name must match AppMutex in installer/Rudi.iss so Inno Setup can detect
# a running instance during install/uninstall and offer to close it.
SINGLETON_MUTEX_NAME = "RudiSingletonMutex"
_SINGLETON_MUTEX_HANDLE = None


def _acquire_singleton_mutex() -> None:
    """Create a Windows named mutex the installer can poll.

    The handle is stashed on a module global so Python doesn't GC it — the OS
    releases the mutex automatically when the process exits. Never blocks or
    refuses startup; a pre-existing mutex just means the installer will see
    "Rudi is running" and prompt the user.
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


class MainWindow(QMainWindow):
    def __init__(self, api: ApiClient, server_host: str, server_port: int):
        super().__init__()
        self.setWindowTitle(f"Rudi v{__version__}")
        self.setMinimumSize(1000, 700)

        self.server_host = server_host
        self.server_port = server_port
        self.api = api

        self._build_ui()
        self._build_menu()
        self.statusBar().showMessage(f"Connected to server at {api.base_url}")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._apply_default_view)

    def _build_ui(self):
        # Tabs for content management
        self.question_pool = QuestionPool(self.api)
        self.quiz_builder = QuizBuilder(self.api)
        # Topics now live in the Settings dialog; the Question pool exposes a
        # button that asks us to open it on the Topics tab.
        if hasattr(self.question_pool, "topics_requested"):
            self.question_pool.topics_requested.connect(self._open_topics_settings)

        # Game panel is the main window's central widget
        self.game_panel = GameControlPanel(
            self.api,
            server_host=self.server_host,
            server_port=self.server_port,
        )
        self.setCentralWidget(self.game_panel)

        # Dock widgets for authoring tools
        self.dock_questions = self._make_dock("Questions", self.question_pool)
        self.dock_quizzes = self._make_dock("Quiz Builder", self.quiz_builder)

        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_questions)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock_quizzes)
        # Stack them as tabs in the same dock area to save space
        self.tabifyDockWidget(self.dock_questions, self.dock_quizzes)
        self.dock_questions.raise_()

        # Start with all authoring docks hidden so the Game panel has full space;
        # the View menu lets the instructor show them on demand.
        for dock in (self.dock_questions, self.dock_quizzes):
            dock.hide()

        # Right-side dockable runtime panels: Leaderboard and Server Console.
        # Built inside GameControlPanel; MainWindow owns the QDockWidget
        # wrappers so they can be toggled/moved/floated.
        self.dock_leaderboard = self._make_dock(
            "Live Leaderboard", self.game_panel.leaderboard_group,
        )
        self.dock_server_console = self._make_dock(
            "Server Console", self.game_panel.server_console_group,
        )
        for dock in (self.dock_leaderboard, self.dock_server_console):
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self.splitDockWidget(
            self.dock_leaderboard, self.dock_server_console,
            Qt.Orientation.Vertical,
        )

        status = QStatusBar()
        self.setStatusBar(status)

    def _apply_default_view(self):
        """Canonical layout: left authoring docks hidden, right runtime docks
        visible and sized in equal thirds."""
        for dock in (self.dock_questions, self.dock_quizzes):
            dock.hide()
        right_docks = (self.dock_leaderboard, self.dock_server_console)
        for dock in right_docks:
            # Un-float and re-dock if the user had torn it out.
            if dock.isFloating():
                dock.setFloating(False)
            if self.dockWidgetArea(dock) != Qt.DockWidgetArea.RightDockWidgetArea:
                self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            dock.show()
        # Re-establish the vertical split in case the user tabified them.
        self.splitDockWidget(
            self.dock_leaderboard, self.dock_server_console,
            Qt.Orientation.Vertical,
        )
        # Size the two right-side docks in equal halves of the window height.
        half = max(100, self.height() // 2)
        self.resizeDocks(
            list(right_docks), [half, half], Qt.Orientation.Vertical,
        )

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

        settings_action = QAction("&Settings\u2026", self)
        settings_action.triggered.connect(self._open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu — dock visibility toggles + projection window toggle
        view_menu = menubar.addMenu("&View")
        for dock in (self.dock_questions, self.dock_quizzes):
            action = dock.toggleViewAction()  # checkable, auto-synced with the dock
            view_menu.addAction(action)

        view_menu.addSeparator()
        for dock in (self.dock_leaderboard, self.dock_server_console):
            view_menu.addAction(dock.toggleViewAction())

        view_menu.addSeparator()

        default_view_action = QAction("&Default View", self)
        default_view_action.triggered.connect(self._apply_default_view)
        view_menu.addAction(default_view_action)

        view_menu.addSeparator()

        self.projection_action = QAction("&Projection Window", self)
        self.projection_action.setCheckable(True)
        self.projection_action.setChecked(self.game_panel.is_projection_visible())
        # Ignore the auto-toggled `checked` arg — toggle_projection() decides
        # the real state from the window's current visibility and emits
        # projection_visibility_changed, which re-syncs the checkmark.
        self.projection_action.triggered.connect(
            lambda _checked: self.game_panel.toggle_projection()
        )
        # Keep the checkmark in sync when the panel opens/closes the window
        # itself (e.g. on New Game).
        self.game_panel.projection_visibility_changed.connect(
            self.projection_action.setChecked,
        )
        view_menu.addAction(self.projection_action)


    def _open_settings(self, initial_tab: int = SettingsWindow.TAB_TOPICS):
        dlg = SettingsWindow(self.api, self, initial_tab=initial_tab)
        dlg.exec()
        # Topic edits may affect the Questions panel's topic filter and any
        # topic-name cells; refresh once the dialog closes.
        try:
            self.question_pool.refresh()
        except Exception:
            pass

    def _open_topics_settings(self):
        self._open_settings(SettingsWindow.TAB_TOPICS)

    def closeEvent(self, event):
        # ProjectionWindow is a parentless top-level window, so closing the
        # main window doesn't cascade to it. Close it explicitly.
        proj = getattr(self.game_panel, "projection_window", None)
        if proj is not None:
            proj.close()
            self.game_panel.projection_window = None
        # Tear down the WS thread the game panel owns.
        if getattr(self.game_panel, "ws_thread", None) is not None:
            try:
                self.game_panel.ws_thread.stop()
                self.game_panel.ws_thread.wait(1000)
            except Exception:
                pass
        self.api.close()
        event.accept()


def main():
    # Claim the named mutex before anything heavy so a parallel installer run
    # can see "Rudi is running" as soon as possible.
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

    from instructor.ui.splash_screen import StartupDialog
    splash = StartupDialog()
    splash.exec()
    if splash.api_client is None:
        sys.exit(0)

    conn = splash.conn
    window = MainWindow(
        api=splash.api_client,
        server_host=conn["server_host"],
        server_port=conn["server_port"],
    )
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
