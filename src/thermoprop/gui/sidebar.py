"""
The application's navigation rail.

Five destinations in a fixed order, each with its label and its icon. The
rail is a list of places rather than a row of buttons: labels align in a
column, the current page is marked by fill *and* weight *and* ink so the
selection never rests on a background tint alone, and the whole thing can be
narrowed or hidden when the content needs the width.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QSizePolicy, QWidget

from . import layout as ly
from .icons import icon
from .theme import Tokens

# key, label, icon name. The order is the navigation order.
PAGES = (
    ("single_point", "Single point", "crosshair"),
    ("mixture", "Mixture", "blend"),
    ("saturation", "Saturation", "droplet"),
    ("process_path", "Process path", "trending-up"),
    ("plotting", "Plotting", "chart-line"),
)


class Sidebar(QWidget):
    """Vertical navigation. Emits the index of the page the user picked."""

    selected = Signal(int)

    MIN_W = 168      # the longest label plus its icon, without eliding
    DEFAULT_W = 220

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setMinimumWidth(self.MIN_W)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        panel = ly.vbox(self, margin=Tokens.SPACING_ROW,
                        spacing=Tokens.SPACING_GROUP)

        brand = ly.brand("ThermoProp")
        brand.setContentsMargins(Tokens.SPACING_ROW, Tokens.SPACING_ROW,
                                 Tokens.SPACING_ROW, 0)
        panel.addWidget(brand)

        nav = ly.vbox(spacing=2)   # destinations are one list, so tight
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = []

        for index, (key, label, glyph) in enumerate(PAGES):
            button = ly.button(label, variant="nav")
            button.setCheckable(True)
            button.setIcon(icon(glyph))
            button.setIconSize(QSize(Tokens.ICON_SIZE, Tokens.ICON_SIZE))
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            button.setToolTip(label)
            button.clicked.connect(
                lambda _checked, i=index: self.selected.emit(i))
            self._group.addButton(button, index)
            self._buttons.append(button)
            nav.addWidget(button)

        panel.addLayout(nav)
        panel.addStretch()

        self._buttons[0].setChecked(True)

    def set_current(self, index: int) -> None:
        """Mark a page as current without re-emitting the selection."""
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def current(self) -> int:
        return self._group.checkedId()
