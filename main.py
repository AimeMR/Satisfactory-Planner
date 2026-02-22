"""
main.py
Application entry point — Phase 2+ (Qt GUI).

Launches the PySide6 application, initialises the DB, and opens MainWindow.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui     import QFont

from database.db       import initialize_db, close_connection
from database.seed_data import seed_db
from ui.main_window    import MainWindow


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Database bootstrap
    # ------------------------------------------------------------------
    initialize_db()
    seed_db()

    # ------------------------------------------------------------------
    # 2. Qt application
    # ------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName("Satisfactory Planner")
    app.setOrganizationName("AimeMR")

    # Global font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # ------------------------------------------------------------------
    # 3. Main window
    # ------------------------------------------------------------------
    window = MainWindow()
    window.show()

    exit_code = app.exec()

    # ------------------------------------------------------------------
    # 4. Cleanup
    # ------------------------------------------------------------------
    close_connection()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
