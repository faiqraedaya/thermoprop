"""
THERMOPROP
Thermophysical Properties Calculator

Application entry point.
"""

import logging
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow

__version__ = "2.4.0"


def main():
    """Main application entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ThermoProp")
    app.setApplicationVersion(__version__)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
