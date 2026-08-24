"""
The application's single icon family.

One set, one stroke weight, one size. The glyphs are Lucide geometry drawn
on Lucide's native 24 px grid and rendered down to the 16 px icon token, with
the stroke widened to 2.25 so that it lands at exactly 1.5 px once scaled.

Icons are tinted from the ink ladder rather than shipped as coloured assets,
so a new rung in ``theme.py`` reaches them without touching any artwork. An
icon is never the only carrier of meaning here - every one of these sits
beside its own text label.
"""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .theme import Tokens

# Lucide paths on a 24x24 grid. Keep new entries in the same idiom: round
# caps and joins, geometric construction, no fills.
_GLYPHS = {
    # A single state fixed by crossing coordinates
    "crosshair": (
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="22" y1="12" x2="18" y2="12"/>'
        '<line x1="6" y1="12" x2="2" y2="12"/>'
        '<line x1="12" y1="6" x2="12" y2="2"/>'
        '<line x1="12" y1="22" x2="12" y2="18"/>'
    ),
    # Two components overlapping
    "blend": (
        '<circle cx="9" cy="9" r="7"/>'
        '<circle cx="15" cy="15" r="7"/>'
    ),
    # Liquid and vapour in equilibrium
    "droplet": (
        '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5'
        'c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>'
    ),
    # A path travelled between two states
    "trending-up": (
        '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/>'
        '<polyline points="16 7 22 7 22 13"/>'
    ),
    # Axes with a plotted trace
    "chart-line": (
        '<path d="M3 3v16a2 2 0 0 0 2 2h16"/>'
        '<path d="m19 9-5 5-4-4-3 3"/>'
    ),
    # The sidebar toggle: a panel with its rail marked
    "panel-left": (
        '<rect width="18" height="18" x="3" y="3" rx="2"/>'
        '<path d="M9 3v18"/>'
    ),
}

_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
    'fill="none" stroke="{colour}" stroke-width="2.25" '
    'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)


def _pixmap(name: str, colour: str, size: int, ratio: float) -> QPixmap:
    """Render one glyph at the given device pixel ratio."""
    svg = _SVG.format(colour=colour, body=_GLYPHS[name])
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))

    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    # Render into an explicit logical rect: with no target given, the SVG is
    # laid out against the pixmap's device rect and the glyph overflows its
    # box by the device pixel ratio.
    renderer.setAspectRatioMode(Qt.KeepAspectRatio)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def icon(name: str, *, size: int = 0, ratio: float = 2.0) -> QIcon:
    """An icon that sits at glyph alpha and promotes when active.

    Qt picks the ``On`` pixmap for a checked button and the ``Active`` one
    under the mouse, so a nav item's icon brightens with its label instead
    of staying flat while the text around it changes.
    """
    if name not in _GLYPHS:
        raise KeyError(
            f"No '{name}' in the icon set. Add it to _GLYPHS in Lucide's "
            f"idiom, or use a text label - never reach for a second family."
        )
    size = size or Tokens.ICON_SIZE
    rest = Tokens.ink_hex(Tokens.INK_GLYPH)
    active = Tokens.ink_hex(Tokens.INK_SECONDARY)
    selected = Tokens.ink_hex(Tokens.INK_PRIMARY)

    result = QIcon()
    result.addPixmap(_pixmap(name, rest, size, ratio),
                     QIcon.Normal, QIcon.Off)
    result.addPixmap(_pixmap(name, active, size, ratio),
                     QIcon.Active, QIcon.Off)
    result.addPixmap(_pixmap(name, selected, size, ratio),
                     QIcon.Normal, QIcon.On)
    result.addPixmap(_pixmap(name, selected, size, ratio),
                     QIcon.Active, QIcon.On)
    result.addPixmap(_pixmap(name, Tokens.ink_hex(Tokens.INK_DISABLED),
                             size, ratio), QIcon.Disabled, QIcon.Off)
    return result
