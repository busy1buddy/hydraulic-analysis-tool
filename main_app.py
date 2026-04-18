"""
Hydraulic Analysis Tool — Entry Point
=======================================
Launch the PyQt6 desktop application.

Usage:
    python main_app.py
    python main_app.py path/to/network.inp
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from desktop.main_window import MainWindow
from desktop.crash_dialog import CrashDialog


def exception_hook(exctype, value, tb):
    """Global exception handler to show CrashDialog."""
    print(f"CRITICAL ERROR: {exctype} - {value}")
    try:
        if QApplication.instance():
            dlg = CrashDialog(value, tb)
            dlg.exec()
        else:
            import traceback
            traceback.print_exception(exctype, value, tb)
    except:
        pass
    sys.__excepthook__(exctype, value, tb)


def main():
    sys.excepthook = exception_hook
    app = QApplication(sys.argv)
    app.setApplicationName("Hydraulic Analysis Tool")
    app.setOrganizationName("HydraulicTool")

    # Dark theme stylesheet
    app.setStyleSheet("""
        QMainWindow { background-color: #1e1e2e; }
        QDockWidget { color: #cdd6f4; }
        QDockWidget::title {
            background-color: #313244;
            color: #cdd6f4;
            padding: 6px;
        }
        QTreeWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: 1px solid #313244;
            font-family: Consolas;
        }
        QTreeWidget::item:selected {
            background-color: #45475a;
        }
        QTableWidget {
            background-color: #1e1e2e;
            color: #cdd6f4;
            border: 1px solid #313244;
            gridline-color: #313244;
        }
        QTableWidget::item:selected {
            background-color: #45475a;
        }
        QHeaderView::section {
            background-color: #313244;
            color: #cdd6f4;
            padding: 4px;
            border: 1px solid #45475a;
        }
        QMenuBar {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
        QMenuBar::item:selected {
            background-color: #45475a;
        }
        QMenu {
            background-color: #313244;
            color: #cdd6f4;
        }
        QMenu::item:selected {
            background-color: #45475a;
        }
        QStatusBar {
            background-color: #181825;
            color: #a6adc8;
        }
        QLabel {
            color: #cdd6f4;
        }
        QSplitter::handle {
            background-color: #313244;
        }
        QMessageBox {
            background-color: #1e1e2e;
            color: #cdd6f4;
        }
    """)

    window = MainWindow()

    # If a file was passed as argument, open it. Otherwise restore the
    # last-opened file from saved preferences (session persistence).
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if os.path.isfile(filepath) and filepath.endswith('.inp'):
            window.api.load_network_from_path(os.path.abspath(filepath))
            window._current_file = os.path.abspath(filepath)
            window._populate_explorer()
            window._update_status_bar()
            window.canvas.set_api(window.api)
            window.what_if_panel.set_api(window.api)
            window.setWindowTitle(
                f"Hydraulic Analysis Tool — {os.path.basename(filepath)}"
            )
    else:
        window._restore_session()

    window.show()

    # Show welcome dialog for first-time users (after window is visible)
    window.show_welcome_if_needed()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
