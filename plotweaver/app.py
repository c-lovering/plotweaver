import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .settings import app_settings
from .ui.mainwindow import MainWindow
from .ui.theme import DEFAULT_THEME, apply_theme

ICON = Path(__file__).resolve().parent / "resources" / "icon.png"


def run() -> int:
    if sys.platform.startswith("win"):
        # Group the taskbar button under Plotweaver's own icon instead of Python's.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Plotweaver.Plotweaver")
        except (AttributeError, OSError):
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Plotweaver")
    app.setOrganizationName("Plotweaver")
    app.setDesktopFileName("plotweaver")
    if ICON.exists():
        app.setWindowIcon(QIcon(str(ICON)))
    apply_theme(app, app_settings().value("theme", DEFAULT_THEME, str))
    w = MainWindow()
    w.show()
    return app.exec()
