"""
Unified PySide6 theme - single authority for every colour, metric, and stylesheet.

Usage:
    from .gui.theme import apply_theme, Tokens, restyle

    # In main():
    apply_theme(app)                        # once, after QApplication is created

    # Mark a widget variant:
    button.setProperty("variant", "primary")
    restyle(button)

    # Access tokens directly:
    Tokens.ink(0.64)                        # secondary text colour string
    Tokens.RADIUS                           # border radius in px

Run standalone to print the contrast ladder and verify WCAG ratios:
    python -m thermoprop.gui.theme
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QWidget

logger = logging.getLogger(__name__)

# Inter ships with the app rather than being assumed present on the host,
# so every machine renders the same type scale. A PyInstaller bundle
# unpacks the faces beside this module, so the frozen root is checked too.
def _fonts_dir() -> Path:
    beside_module = Path(__file__).parent / "fonts"
    if beside_module.is_dir():
        return beside_module
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "thermoprop" / "gui" / "fonts"
    return beside_module


FONTS_DIR = _fonts_dir()


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Tokens:
    """All visual constants. Override by subclassing, not patching."""

    # -- Canvas & ink -------------------------------------------------------
    CANVAS: str = "#FFFFFF"
    INK: str = "#000000"

    # -- Ink ladder (alpha on canvas) ---------------------------------------
    # fmt: off
    INK_PRIMARY:   float = 1.00   # values, headings, active labels
    INK_SECONDARY: float = 0.64   # supporting text, inactive tabs
    INK_TERTIARY:  float = 0.56   # units, captions, metadata, placeholder text
    INK_GLYPH:     float = 0.44   # icons, dividers - never text
    INK_DISABLED:  float = 0.38   # inactive controls only
    # fmt: on

    # -- Surface alphas (ink over canvas) -----------------------------------
    SURFACE_BORDER: float = 0.10
    SURFACE_BORDER_STRONG: float = 0.18
    SURFACE_WASH: float = 0.03
    SURFACE_HOVER: float = 0.05
    SURFACE_PRESSED: float = 0.09
    SURFACE_SELECTED: float = 0.09

    # -- Semantic colours ---------------------------------------------------
    ACTION: str = "#2563EB"       # blue - primary action, checked toggles
    ACTION_HOVER: str = "#1D4ED8"
    ACTION_PRESSED: str = "#1E40AF"
    ACTION_TEXT: str = "#FFFFFF"

    SUCCESS: str = "#16A34A"      # green - success states
    SUCCESS_BG: str = "#F0FDF4"
    WARNING: str = "#D97706"      # orange - warning states
    WARNING_BG: str = "#FFFBEB"
    ERROR: str = "#DC2626"        # red - failure states
    ERROR_BG: str = "#FEF2F2"
    ERROR_PRESSED: str = "#B91C1C"

    # -- Typography ---------------------------------------------------------
    FONT_FAMILY: str = "Inter"
    FONT_FALLBACK: str = ""       # resolved at apply_theme time

    # Sizes in px - Qt scales with DPI
    FONT_TITLE: int = 22
    FONT_HEADING: int = 16
    FONT_BODY: int = 14
    FONT_LABEL: int = 13
    FONT_CAPTION: int = 12

    WEIGHT_REGULAR: int = 400
    WEIGHT_MEDIUM: int = 500
    WEIGHT_SEMIBOLD: int = 600

    # -- Geometry (8px grid) ------------------------------------------------
    MARGIN_WINDOW: int = 20
    MARGIN_GROUP: int = 16
    SPACING_ROW: int = 8
    SPACING_GROUP: int = 20
    SPACING_SECTION: int = 32

    CONTROL_HEIGHT: int = 32
    CONTROL_COMPACT: int = 26
    RADIUS: int = 6
    RADIUS_PANEL: int = 8
    ICON_SIZE: int = 16

    MIN_WINDOW_W: int = 480
    MIN_WINDOW_H: int = 360
    MIN_DIALOG_W: int = 360

    # Minimum width for a value-entry control, so long numbers never clip
    FIELD_MIN_W: int = 128

    # -- Splitter -----------------------------------------------------------
    SPLITTER_VISUAL: int = 1      # visible line width
    SPLITTER_GRAB: int = 8        # total grab area (transparent padding)

    # -- Motion -------------------------------------------------------------
    DURATION_MS: int = 150
    animate: ClassVar[bool] = True

    # -- Data series --------------------------------------------------------
    # Categorical slots in FIXED order - never cycled, never reordered. Slots
    # 1-3 are the prefix validated for all-pairs use on a light surface; a
    # chart needing a fourth identity folds into "Other" or becomes small
    # multiples rather than inventing a hue.
    SERIES: tuple = ("#2A78D6", "#EB6834", "#1BAF7A")

    # Sequential blue ramp for ORDERED magnitude (e.g. a fan of isobars).
    # Starts at step 250 - the lightest step that still clears 2:1 on white.
    SERIES_SEQUENTIAL: tuple = ("#86B6EF", "#5598E7", "#2A78D6", "#1C5CAB", "#104281")

    # -- Helpers ------------------------------------------------------------
    def ink(self, alpha: float) -> str:
        """Return rgba() string for ink at given alpha."""
        c = QColor(self.INK)
        return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"

    def surface(self, alpha: float) -> str:
        """Return rgba() string for a surface (ink over canvas)."""
        return self.ink(alpha)

    def ink_hex(self, alpha: float) -> str:
        """Return an ink ladder rung flattened to an opaque hex colour.

        For libraries that cannot read rgba() - matplotlib, pyqtgraph.
        """
        return _alpha_blend(self.INK, self.CANVAS, alpha)

    def series(self, index: int) -> str:
        """Return the categorical series colour for a fixed slot index."""
        if not 0 <= index < len(self.SERIES):
            raise IndexError(
                f"Series slot {index} is out of range. The palette has "
                f"{len(self.SERIES)} validated slots; fold further series "
                f"into 'Other' or use small multiples rather than "
                f"inventing a hue."
            )
        return self.SERIES[index]

    def sequential_ink(self, index: int, count: int) -> str:
        """An ordered ramp in neutral ink, for reference contours.

        Contour lines you read a value off - a fan of isobars - are ordered
        chart chrome, not identities. Giving them a hue would collide with
        the categorical series sharing the axes.
        """
        lo, hi = self.INK_GLYPH * 0.6, self.INK_SECONDARY
        if count <= 1:
            return self.ink_hex((lo + hi) / 2)
        return self.ink_hex(lo + (hi - lo) * index / (count - 1))

    def sequential(self, index: int, count: int) -> str:
        """Return a step of the sequential ramp for item `index` of `count`."""
        ramp = self.SERIES_SEQUENTIAL
        if count <= 1:
            return ramp[len(ramp) // 2]
        pos = round(index * (len(ramp) - 1) / (count - 1))
        return ramp[pos]

    @staticmethod
    def pt(px: float, dpi: int = 100) -> float:
        """Convert a px type-scale token to matplotlib points at `dpi`.

        Qt sizes text in px; matplotlib sizes it in points. Without this the
        same token renders ~39 % larger inside a figure than beside it.
        """
        return px * 72.0 / dpi

    def font_css(self) -> str:
        parts = [f'"{self.FONT_FAMILY}"']
        if self.FONT_FALLBACK and self.FONT_FALLBACK != self.FONT_FAMILY:
            parts.append(f'"{self.FONT_FALLBACK}"')
        parts.append("sans-serif")
        return ", ".join(parts)


Tokens = _Tokens()


# ---------------------------------------------------------------------------
# Contrast verification
# ---------------------------------------------------------------------------

def _relative_luminance(hex_colour: str) -> float:
    """WCAG 2.x relative luminance from sRGB hex."""
    c = QColor(hex_colour)
    channels = []
    for v in (c.redF(), c.greenF(), c.blueF()):
        channels.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(l1: float, l2: float) -> float:
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _alpha_blend(fg_hex: str, bg_hex: str, alpha: float) -> str:
    fg, bg = QColor(fg_hex), QColor(bg_hex)
    r = int(fg.red() * alpha + bg.red() * (1 - alpha))
    g = int(fg.green() * alpha + bg.green() * (1 - alpha))
    b = int(fg.blue() * alpha + bg.blue() * (1 - alpha))
    return f"#{r:02X}{g:02X}{b:02X}"


def check_ladder() -> list:
    """Print and return contrast ratios for the ink ladder."""
    canvas_lum = _relative_luminance(Tokens.CANVAS)
    rungs = [
        ("Primary",   Tokens.INK_PRIMARY),
        ("Secondary", Tokens.INK_SECONDARY),
        ("Tertiary",  Tokens.INK_TERTIARY),
        ("Glyph",     Tokens.INK_GLYPH),
        ("Disabled",  Tokens.INK_DISABLED),
    ]
    results = []
    for name, alpha in rungs:
        blended = _alpha_blend(Tokens.INK, Tokens.CANVAS, alpha)
        lum = _relative_luminance(blended)
        ratio = _contrast_ratio(lum, canvas_lum)
        results.append({"name": name, "alpha": alpha, "hex": blended, "ratio": ratio})
        print(f"  {name:12s}  a={alpha:.2f}  {blended}  {ratio:.1f}:1")
    return results


# ---------------------------------------------------------------------------
# QSS builder
# ---------------------------------------------------------------------------

def _build_qss() -> str:
    T = Tokens
    f = T.font_css()

    # ComboBox arrow sizes scale from icon size token
    arrow_half = T.ICON_SIZE // 4          # horizontal wing
    arrow_height = T.ICON_SIZE // 4 + 1    # vertical extent
    grab_pad = (T.SPLITTER_GRAB - T.SPLITTER_VISUAL) // 2

    return f"""
/* -- Global ------------------------------------------------ */
* {{
    font-family: {f};
    font-size: {T.FONT_BODY}px;
    font-weight: {T.WEIGHT_REGULAR};
    color: {T.ink(T.INK_PRIMARY)};
    outline: none;
}}

/* -- Window ------------------------------------------------ */
QMainWindow, QDialog, QWidget#centralWidget {{
    background: {T.CANVAS};
}}

/* -- Labels ------------------------------------------------ */
QLabel {{
    background: transparent;
    padding: 0px;
    border: none;
}}
QLabel[role="title"] {{
    font-size: {T.FONT_TITLE}px;
    font-weight: {T.WEIGHT_SEMIBOLD};
}}
QLabel[role="heading"] {{
    font-size: {T.FONT_HEADING}px;
    font-weight: {T.WEIGHT_SEMIBOLD};
}}
QLabel[role="brand"] {{
    font-size: {T.FONT_HEADING}px;
    font-weight: {T.WEIGHT_SEMIBOLD};
    color: {T.ink(T.INK_PRIMARY)};
}}
QLabel[role="caption"] {{
    font-size: {T.FONT_CAPTION}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.ink(T.INK_TERTIARY)};
}}
QLabel[role="unit"] {{
    font-size: {T.FONT_CAPTION}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.ink(T.INK_TERTIARY)};
}}
/* Status roles - always paired with words, never colour alone */
QLabel[role="error"] {{
    font-size: {T.FONT_CAPTION}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.ERROR};
    background: {T.ERROR_BG};
    border-radius: {T.RADIUS}px;
    padding: 6px 10px;
}}
QLabel[role="success"] {{
    font-size: {T.FONT_CAPTION}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.SUCCESS};
    background: {T.SUCCESS_BG};
    border-radius: {T.RADIUS}px;
    padding: 6px 10px;
}}
QLabel[role="warning"] {{
    font-size: {T.FONT_CAPTION}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.WARNING};
    background: {T.WARNING_BG};
    border-radius: {T.RADIUS}px;
    padding: 6px 10px;
}}

/* -- Inputs ------------------------------------------------ */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {T.CANVAS};
    border: 1px solid {T.ink(T.SURFACE_BORDER)};
    border-radius: {T.RADIUS}px;
    padding: 6px 10px;
    min-height: {T.CONTROL_HEIGHT - 14}px;
    font-size: {T.FONT_BODY}px;
    color: {T.ink(T.INK_PRIMARY)};
    selection-background-color: {T.ink(T.SURFACE_SELECTED)};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
    border-color: {T.ink(T.SURFACE_BORDER_STRONG)};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 2px solid {T.ink(T.INK_GLYPH)};
    padding: 5px 9px;
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{
    background: {T.ink(T.SURFACE_WASH)};
    color: {T.ink(T.INK_DISABLED)};
    border-color: {T.ink(T.SURFACE_BORDER)};
}}
/* Read-only output field: reads as a value, not as somewhere to type */
QDoubleSpinBox[readOnlyValue="true"], QLineEdit[readOnlyValue="true"],
QTextEdit[readOnlyValue="true"] {{
    background: {T.ink(T.SURFACE_WASH)};
}}

/* -- Buttons ----------------------------------------------- */
QPushButton {{
    background: {T.CANVAS};
    border: 1px solid {T.ink(T.SURFACE_BORDER)};
    border-radius: {T.RADIUS}px;
    padding: 6px 16px;
    min-height: {T.CONTROL_HEIGHT - 14}px;
    font-size: {T.FONT_LABEL}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.ink(T.INK_PRIMARY)};
}}
QPushButton:hover {{
    background: {T.ink(T.SURFACE_HOVER)};
    border-color: {T.ink(T.SURFACE_BORDER_STRONG)};
}}
QPushButton:pressed {{
    background: {T.ink(T.SURFACE_PRESSED)};
}}
QPushButton:focus {{
    border: 2px solid {T.ink(T.INK_GLYPH)};
    padding: 5px 15px;
}}
QPushButton:disabled {{
    color: {T.ink(T.INK_DISABLED)};
    border-color: {T.ink(T.SURFACE_BORDER)};
    background: {T.ink(T.SURFACE_WASH)};
}}

/* Primary action button */
QPushButton[variant="primary"] {{
    background: {T.ACTION};
    border: 1px solid {T.ACTION};
    color: {T.ACTION_TEXT};
}}
QPushButton[variant="primary"]:hover {{
    background: {T.ACTION_HOVER};
    border-color: {T.ACTION_HOVER};
}}
QPushButton[variant="primary"]:pressed {{
    background: {T.ACTION_PRESSED};
    border-color: {T.ACTION_PRESSED};
}}
QPushButton[variant="primary"]:focus {{
    border: 2px solid {T.ACTION_PRESSED};
    padding: 5px 15px;
}}
QPushButton[variant="primary"]:disabled {{
    background: {T.ink(T.SURFACE_BORDER)};
    border-color: {T.ink(T.SURFACE_BORDER)};
    color: {T.ink(T.INK_DISABLED)};
}}

/* Quiet / tertiary button */
QPushButton[variant="quiet"] {{
    background: transparent;
    border: none;
    color: {T.ink(T.INK_SECONDARY)};
}}
QPushButton[variant="quiet"]:hover {{
    background: {T.ink(T.SURFACE_HOVER)};
    color: {T.ink(T.INK_PRIMARY)};
}}
QPushButton[variant="quiet"]:pressed {{
    background: {T.ink(T.SURFACE_PRESSED)};
}}
QPushButton[variant="quiet"]:focus {{
    border: 2px solid {T.ink(T.INK_GLYPH)};
    padding: 4px 14px;
}}
QPushButton[variant="quiet"]:disabled {{
    background: transparent;
    color: {T.ink(T.INK_DISABLED)};
}}

/* Danger button */
QPushButton[variant="danger"] {{
    background: {T.CANVAS};
    border: 1px solid {T.ERROR};
    color: {T.ERROR};
}}
QPushButton[variant="danger"]:hover {{
    background: {T.ERROR};
    color: {T.ACTION_TEXT};
}}
QPushButton[variant="danger"]:pressed {{
    background: {T.ERROR_PRESSED};
    border-color: {T.ERROR_PRESSED};
    color: {T.ACTION_TEXT};
}}
QPushButton[variant="danger"]:focus {{
    border: 2px solid {T.ERROR_PRESSED};
    padding: 5px 15px;
}}

/* -- ComboBox dropdown ------------------------------------- */
QComboBox::drop-down {{
    border: none;
    width: {T.ICON_SIZE + 8}px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: {arrow_half}px solid transparent;
    border-right: {arrow_half}px solid transparent;
    border-top: {arrow_height}px solid {T.ink(T.INK_GLYPH)};
    width: 0px;
    height: 0px;
}}
QComboBox QAbstractItemView {{
    background: {T.CANVAS};
    border: 1px solid {T.ink(T.SURFACE_BORDER_STRONG)};
    border-radius: {T.RADIUS}px;
    padding: 4px;
    selection-background-color: {T.ink(T.SURFACE_SELECTED)};
    outline: none;
}}

/* -- SpinBox arrows ---------------------------------------- */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 20px;
}}

/* -- Checkbox & Radio -------------------------------------- */
QCheckBox, QRadioButton {{
    spacing: 8px;
    font-size: {T.FONT_BODY}px;
    color: {T.ink(T.INK_PRIMARY)};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: {T.ICON_SIZE}px;
    height: {T.ICON_SIZE}px;
    border: 1px solid {T.ink(T.SURFACE_BORDER_STRONG)};
    background: {T.CANVAS};
}}
QCheckBox::indicator {{
    border-radius: 3px;
}}
QRadioButton::indicator {{
    border-radius: {T.ICON_SIZE // 2}px;
}}
QCheckBox::indicator:checked {{
    background: {T.ACTION};
    border-color: {T.ACTION};
}}
QRadioButton::indicator:checked {{
    background: {T.ACTION};
    border-color: {T.ACTION};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {T.ink(T.INK_GLYPH)};
}}
QCheckBox::indicator:focus, QRadioButton::indicator:focus {{
    border: 2px solid {T.ink(T.INK_GLYPH)};
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {T.ink(T.INK_DISABLED)};
}}

/* -- GroupBox ---------------------------------------------- */
QGroupBox {{
    font-size: {T.FONT_LABEL}px;
    font-weight: {T.WEIGHT_SEMIBOLD};
    color: {T.ink(T.INK_PRIMARY)};
    border: 1px solid {T.ink(T.SURFACE_BORDER)};
    border-radius: {T.RADIUS_PANEL}px;
    margin-top: 12px;
    padding: {T.MARGIN_GROUP}px;
    padding-top: 28px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {T.MARGIN_GROUP}px;
    padding: 0 6px;
    background: {T.CANVAS};
}}

/* -- TabWidget --------------------------------------------- */
QTabWidget::pane {{
    border: 1px solid {T.ink(T.SURFACE_BORDER)};
    border-radius: {T.RADIUS_PANEL}px;
    background: {T.CANVAS};
    padding: {T.MARGIN_GROUP}px;
}}
/* Nested tabs: the outer pane already draws the boundary, so a second
   outline around the same content would be a double border. */
QTabWidget[variant="inner"]::pane {{
    border: none;
    border-top: 1px solid {T.ink(T.SURFACE_BORDER)};
    border-radius: 0px;
    padding: {T.SPACING_ROW}px 0px 0px 0px;
}}
QTabBar::tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 16px;
    font-size: {T.FONT_LABEL}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.ink(T.INK_SECONDARY)};
}}
QTabBar::tab:selected {{
    color: {T.ink(T.INK_PRIMARY)};
    border-bottom-color: {T.ink(T.INK_PRIMARY)};
}}
QTabBar::tab:hover:!selected {{
    color: {T.ink(T.INK_PRIMARY)};
    background: {T.ink(T.SURFACE_HOVER)};
}}
QTabBar::tab:focus {{
    border-bottom: 2px solid {T.ink(T.INK_GLYPH)};
    color: {T.ink(T.INK_PRIMARY)};
}}

/* -- Table ------------------------------------------------- */
QTableView, QTreeView, QListView {{
    background: {T.CANVAS};
    border: 1px solid {T.ink(T.SURFACE_BORDER)};
    border-radius: {T.RADIUS}px;
    gridline-color: transparent;
    alternate-background-color: {T.ink(T.SURFACE_WASH)};
    selection-background-color: {T.ink(T.SURFACE_SELECTED)};
    selection-color: {T.ink(T.INK_PRIMARY)};
    font-size: {T.FONT_BODY}px;
    outline: none;
}}
QTableView::item, QTreeView::item, QListView::item {{
    padding: 6px 10px;
    border: none;
}}
QTableView:focus, QTreeView:focus, QListView:focus {{
    border: 2px solid {T.ink(T.INK_GLYPH)};
}}
QHeaderView::section {{
    background: {T.ink(T.SURFACE_WASH)};
    border: none;
    border-bottom: 1px solid {T.ink(T.SURFACE_BORDER)};
    padding: 6px 10px;
    font-size: {T.FONT_CAPTION}px;
    font-weight: {T.WEIGHT_SEMIBOLD};
    color: {T.ink(T.INK_SECONDARY)};
}}
QTableCornerButton::section {{
    background: {T.ink(T.SURFACE_WASH)};
    border: none;
    border-bottom: 1px solid {T.ink(T.SURFACE_BORDER)};
}}

/* -- Scrollbar --------------------------------------------- */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {T.ink(T.INK_GLYPH)};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background: {T.ink(T.INK_TERTIARY)};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0px;
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {T.ink(T.INK_GLYPH)};
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {T.ink(T.INK_TERTIARY)};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0px;
    background: transparent;
}}

/* -- ToolTip ----------------------------------------------- */
QToolTip {{
    background: {T.ink(0.92)};
    color: {T.CANVAS};
    border: none;
    border-radius: {T.RADIUS}px;
    padding: 6px 10px;
    font-size: {T.FONT_CAPTION}px;
}}

/* -- StatusBar --------------------------------------------- */
QStatusBar {{
    background: {T.CANVAS};
    border-top: 1px solid {T.ink(T.SURFACE_BORDER)};
    font-size: {T.FONT_CAPTION}px;
    color: {T.ink(T.INK_TERTIARY)};
    padding: 4px {T.MARGIN_WINDOW}px;
}}
QStatusBar::item {{
    border: none;
}}
QStatusBar QLabel {{
    font-size: {T.FONT_CAPTION}px;
    color: {T.ink(T.INK_TERTIARY)};
}}

/* -- ProgressBar ------------------------------------------- */
QProgressBar {{
    background: {T.ink(T.SURFACE_WASH)};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    font-size: 0px;
}}
QProgressBar::chunk {{
    background: {T.ACTION};
    border-radius: 3px;
}}

/* -- Slider ------------------------------------------------ */
QSlider::groove:horizontal {{
    background: {T.ink(T.SURFACE_BORDER)};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {T.ink(T.INK_PRIMARY)};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {T.ACTION};
}}

/* -- Splitter ---------------------------------------------- */
QSplitter::handle {{
    background: {T.ink(T.SURFACE_BORDER)};
}}
QSplitter::handle:hover {{
    background: {T.ink(T.SURFACE_BORDER_STRONG)};
}}
QSplitter::handle:horizontal {{
    width: {T.SPLITTER_VISUAL}px;
    margin: 0 {grab_pad}px;
}}
QSplitter::handle:vertical {{
    height: {T.SPLITTER_VISUAL}px;
    margin: {grab_pad}px 0;
}}

/* -- Menu -------------------------------------------------- */
QMenuBar {{
    background: {T.CANVAS};
    border-bottom: 1px solid {T.ink(T.SURFACE_BORDER)};
    padding: 2px 8px;
    font-size: {T.FONT_LABEL}px;
}}
QMenuBar::item {{
    padding: 6px 10px;
    border-radius: {T.RADIUS}px;
    color: {T.ink(T.INK_PRIMARY)};
}}
QMenuBar::item:selected {{
    background: {T.ink(T.SURFACE_HOVER)};
}}
QMenu {{
    background: {T.CANVAS};
    border: 1px solid {T.ink(T.SURFACE_BORDER_STRONG)};
    border-radius: {T.RADIUS_PANEL}px;
    padding: 4px;
    font-size: {T.FONT_LABEL}px;
}}
QMenu::item {{
    padding: 6px 28px 6px 12px;
    border-radius: {T.RADIUS - 2}px;
    color: {T.ink(T.INK_PRIMARY)};
}}
QMenu::item:selected {{
    background: {T.ink(T.SURFACE_HOVER)};
}}
QMenu::item:disabled {{
    color: {T.ink(T.INK_DISABLED)};
}}
QMenu::separator {{
    height: 1px;
    background: {T.ink(T.SURFACE_BORDER)};
    margin: 4px 8px;
}}

/* -- Toolbar ----------------------------------------------- */
QToolBar {{
    background: {T.CANVAS};
    border-bottom: 1px solid {T.ink(T.SURFACE_BORDER)};
    spacing: 4px;
    padding: 4px 8px;
}}
QToolButton {{
    background: transparent;
    border: none;
    border-radius: {T.RADIUS}px;
    padding: 6px;
    color: {T.ink(T.INK_SECONDARY)};
}}
QToolButton:hover {{
    background: {T.ink(T.SURFACE_HOVER)};
    color: {T.ink(T.INK_PRIMARY)};
}}
QToolButton:pressed {{
    background: {T.ink(T.SURFACE_PRESSED)};
}}
QToolButton:checked {{
    background: {T.ink(T.SURFACE_SELECTED)};
    color: {T.ink(T.INK_PRIMARY)};
}}

/* -- DialogButtonBox --------------------------------------- */
QDialogButtonBox {{
    dialogbuttonbox-buttons-have-icons: 0;
}}

/* -- Sidebar ----------------------------------------------- */
QWidget#sidebar {{
    background: {T.ink(T.SURFACE_WASH)};
    border: none;
}}
/* Navigation item: the destination list, not a row of buttons. Left
   aligned so the labels form a readable column, and the checked state
   carries weight and ink as well as a fill - never fill alone. */
QPushButton[variant="nav"] {{
    background: transparent;
    border: none;
    border-radius: {T.RADIUS}px;
    padding: 6px 10px;
    min-height: {T.CONTROL_HEIGHT - 12}px;
    text-align: left;
    font-size: {T.FONT_LABEL}px;
    font-weight: {T.WEIGHT_MEDIUM};
    color: {T.ink(T.INK_SECONDARY)};
}}
QPushButton[variant="nav"]:hover {{
    background: {T.ink(T.SURFACE_HOVER)};
    color: {T.ink(T.INK_PRIMARY)};
}}
QPushButton[variant="nav"]:pressed {{
    background: {T.ink(T.SURFACE_PRESSED)};
}}
QPushButton[variant="nav"]:checked {{
    background: {T.ink(T.SURFACE_SELECTED)};
    color: {T.ink(T.INK_PRIMARY)};
    font-weight: {T.WEIGHT_SEMIBOLD};
}}
QPushButton[variant="nav"]:focus {{
    border: 2px solid {T.ink(T.INK_GLYPH)};
    padding: 4px 8px;
}}

/* -- ScrollArea -------------------------------------------- */
QScrollArea {{
    background: {T.CANVAS};
    border: none;
}}
"""


# ---------------------------------------------------------------------------
# Application-level setup
# ---------------------------------------------------------------------------

def load_fonts() -> bool:
    """Register the bundled Inter faces with Qt.

    Returns True if the family is available afterwards. A missing font file
    is logged rather than raised - the app still runs on the platform
    sans-serif, it just does not look like itself.
    """
    if not FONTS_DIR.is_dir():
        logger.warning("Bundled font directory missing: %s", FONTS_DIR)
        return Tokens.FONT_FAMILY in QFontDatabase.families()

    for path in sorted(FONTS_DIR.glob("*.ttf")):
        if QFontDatabase.addApplicationFont(str(path)) == -1:
            logger.warning("Qt refused the bundled font file: %s", path.name)

    return Tokens.FONT_FAMILY in QFontDatabase.families()


def apply_theme(app: QApplication) -> None:
    """Apply the unified theme to a QApplication. Call once after construction."""

    # Resolve font: the bundled Inter first, the platform sans-serif only
    # if registering it failed.
    if load_fonts():
        family = Tokens.FONT_FAMILY
    else:
        family = app.font().family()
        object.__setattr__(Tokens, "FONT_FALLBACK", family)
        logger.warning("Inter unavailable; falling back to %s", family)

    font = QFont(family, Tokens.FONT_BODY)
    font.setWeight(QFont.Weight(Tokens.WEIGHT_REGULAR))
    app.setFont(font)

    # Build and apply QSS
    app.setStyleSheet(_build_qss())

    # Palette for widgets that ignore QSS (native dialogs, some item views)
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(Tokens.CANVAS))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Tokens.INK))
    palette.setColor(QPalette.ColorRole.Base, QColor(Tokens.CANVAS))
    palette.setColor(QPalette.ColorRole.AlternateBase,
                     QColor(Tokens.ink_hex(Tokens.SURFACE_WASH)))
    palette.setColor(QPalette.ColorRole.Text, QColor(Tokens.INK))
    palette.setColor(QPalette.ColorRole.Button, QColor(Tokens.CANVAS))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Tokens.INK))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Tokens.ACTION))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Tokens.ACTION_TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText,
                     QColor(Tokens.ink_hex(Tokens.INK_TERTIARY)))
    app.setPalette(palette)


def restyle(widget: QWidget) -> None:
    """Force a widget to re-read its stylesheet after a property change."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


# ---------------------------------------------------------------------------
# Matplotlib integration
# ---------------------------------------------------------------------------

def _mpl_cycler():
    """Colour cycle over the fixed categorical slots, never a generated hue."""
    from cycler import cycler
    return cycler(color=list(Tokens.SERIES))


def mpl_theme() -> dict:
    """Return an rcParams dict that themes matplotlib to match the app."""
    T = Tokens
    return {
        "figure.facecolor": T.CANVAS,
        "axes.facecolor": T.CANVAS,
        "axes.edgecolor": T.ink_hex(T.INK_GLYPH),
        "axes.labelcolor": T.ink_hex(T.INK_SECONDARY),
        "axes.titlesize": T.pt(T.FONT_LABEL),
        "axes.titlecolor": T.ink_hex(T.INK_PRIMARY),
        "axes.labelsize": T.pt(T.FONT_CAPTION),
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.prop_cycle": _mpl_cycler(),
        "xtick.color": T.ink_hex(T.INK_TERTIARY),
        "ytick.color": T.ink_hex(T.INK_TERTIARY),
        "xtick.labelsize": T.pt(T.FONT_CAPTION),
        "ytick.labelsize": T.pt(T.FONT_CAPTION),
        "xtick.direction": "out",
        "ytick.direction": "out",
        "grid.color": T.ink_hex(T.SURFACE_BORDER),
        "grid.linewidth": 0.5,
        "lines.linewidth": 2.0,
        "lines.markersize": 4,
        "legend.fontsize": T.pt(T.FONT_CAPTION),
        "legend.framealpha": 0,
        "legend.edgecolor": "none",
        "legend.labelcolor": T.ink_hex(T.INK_SECONDARY),
        "font.family": "sans-serif",
        "font.sans-serif": [T.FONT_FAMILY, "Segoe UI", "Arial", "Helvetica"],
        "font.size": T.pt(T.FONT_CAPTION),
        "text.color": T.ink_hex(T.INK_PRIMARY),
        "figure.titlesize": T.pt(T.FONT_HEADING),
        "savefig.facecolor": T.CANVAS,
        "savefig.edgecolor": "none",
    }


def apply_mpl_theme() -> None:
    """Apply the theme to matplotlib globally. Call once."""
    try:
        import matplotlib as mpl
        mpl.rcParams.update(mpl_theme())
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Standalone: verify the contrast ladder
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    print("Ink ladder - contrast against canvas:")
    check_ladder()
    print()

    canvas_lum = _relative_luminance(Tokens.CANVAS)
    for name, hex_val in [
        ("Action", Tokens.ACTION),
        ("Success", Tokens.SUCCESS),
        ("Warning", Tokens.WARNING),
        ("Error", Tokens.ERROR),
    ]:
        lum = _relative_luminance(hex_val)
        print(f"  {name:12s}  {hex_val}  "
              f"{_contrast_ratio(lum, canvas_lum):.1f}:1 on canvas")

    action_lum = _relative_luminance(Tokens.ACTION)
    text_lum = _relative_luminance(Tokens.ACTION_TEXT)
    print(f"  {'Action text':12s}  {Tokens.ACTION_TEXT} on {Tokens.ACTION}  "
          f"{_contrast_ratio(action_lum, text_lum):.1f}:1")

    print()
    print("Data series - contrast against canvas:")
    for i, hex_val in enumerate(Tokens.SERIES, start=1):
        lum = _relative_luminance(hex_val)
        ratio = _contrast_ratio(lum, canvas_lum)
        note = "" if ratio >= 3.0 else "   relief rule: needs a visible label"
        print(f"  slot {i}        {hex_val}  {ratio:.1f}:1{note}")
