"""
THERMOPROP
Thermophysical Properties Calculator

Application entry point.
"""

import logging
import sys

from PySide6.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .gui.theme import apply_mpl_theme, apply_theme

__version__ = "2.6.0"


def main():
    """Main application entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ThermoProp")
    app.setApplicationVersion(__version__)

    # theme.py is the sole styling authority; nothing else sets a stylesheet.
    apply_theme(app)
    apply_mpl_theme()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
