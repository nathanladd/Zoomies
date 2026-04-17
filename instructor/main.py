import sys

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QStatusBar, QMessageBox,
)
from PyQt6.QtCore import Qt

from instructor.api_client import ApiClient
from instructor.core.topic_manager import TopicManager
from instructor.core.question_pool import QuestionPool
from instructor.core.quiz_builder import QuizBuilder
from instructor.core.results_viewer import ResultsViewer
from instructor.games.pointdrop.control_panel import PointDropControlPanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cognit - Educational Assessment Platform")
        self.setMinimumSize(1000, 700)

        self.api = ApiClient()

        self._build_ui()
        self.statusBar().showMessage("Connected to server at localhost:5000")

    def _build_ui(self):
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)

        self.topic_mgr = TopicManager(self.api)
        self.question_pool = QuestionPool(self.api)
        self.quiz_builder = QuizBuilder(self.api)
        self.results_viewer = ResultsViewer(self.api)
        self.pointdrop_panel = PointDropControlPanel(self.api)

        tabs.addTab(self.topic_mgr, "Topics")
        tabs.addTab(self.question_pool, "Questions")
        tabs.addTab(self.quiz_builder, "Quiz Builder")
        tabs.addTab(self.pointdrop_panel, "PointDrop Game")
        tabs.addTab(self.results_viewer, "Results")

        self.setCentralWidget(tabs)

        status = QStatusBar()
        self.setStatusBar(status)

    def closeEvent(self, event):
        self.api.close()
        event.accept()


def main():
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
