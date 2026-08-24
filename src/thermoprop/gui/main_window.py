"""
Main window implementation for ThermoProp application
"""

import json

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QProgressBar, QStackedWidget,
    QWidget,
)

from ..core.file_io import FileIO
from ..core.mixture_calculator import MixtureCalculator
from . import layout as ly
from .icons import icon
from .mixture_dialog import MixtureDialog
from .mixture_tab import MixtureTab
from .plotting_tab import PlottingTab
from .process_path_tab import ProcessPathTab
from .saturation_tab import SaturationTab
from .sidebar import PAGES, Sidebar
from .single_point_tab import SinglePointTab
from .theme import Tokens
from .unit_converter_dialog import UnitConverterDialog

_PAGE_CLASSES = {
    'single_point': SinglePointTab,
    'mixture': MixtureTab,
    'saturation': SaturationTab,
    'process_path': ProcessPathTab,
    'plotting': PlottingTab,
}


class MainWindow(QMainWindow):
    """Main application window with mixture support"""

    # Roomy enough for the widest page (a plot beside its controls) plus the
    # navigation rail, without clipping a control or wrapping a label.
    MIN_W = 1040
    MIN_H = 640

    def __init__(self):
        super().__init__()
        self.calc = MixtureCalculator()
        self.settings = QSettings('ThermoProp', 'Calculator')
        self.current_mixture = []
        self.pages = {}
        self._sidebar_width = Sidebar.DEFAULT_W
        self.init_ui()
        self.load_settings()

    # -- Construction ------------------------------------------------------

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('ThermoProp - Thermophysical properties')
        self.setMinimumSize(self.MIN_W, self.MIN_H)
        self.resize(1400, 900)

        self.create_menu_bar()

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        shell = ly.hbox(central_widget, spacing=0)

        self.sidebar = Sidebar()
        self.sidebar.selected.connect(self.show_page)

        self.splitter = ly.splitter(
            self.sidebar, self._build_content(),
            sizes=[Sidebar.DEFAULT_W, 1400 - Sidebar.DEFAULT_W],
            stretch=[0, 1])
        shell.addWidget(self.splitter)

        self.show_page(0)

        # Status bar: one message, plus a progress bar that only exists while
        # something is actually running.
        self.statusBar().showMessage('Ready')
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumWidth(160)
        self.progress_bar.setMaximumWidth(240)
        self.progress_bar.setVisible(False)
        self.statusBar().addPermanentWidget(self.progress_bar)

    def _build_content(self) -> QWidget:
        """The page area: a header naming the current page, then the page."""
        content, content_layout = ly.panel(margin=Tokens.MARGIN_WINDOW,
                                           spacing=Tokens.SPACING_GROUP)

        header = ly.hbox(spacing=Tokens.SPACING_ROW)
        self.sidebar_toggle = ly.button(
            "", variant="quiet", on_click=self.toggle_sidebar,
            tooltip="Hide the navigation sidebar (Ctrl+B)")
        self.sidebar_toggle.setIcon(icon("panel-left"))
        self.sidebar_toggle.setIconSize(QSize(Tokens.ICON_SIZE,
                                              Tokens.ICON_SIZE))
        self.sidebar_toggle.setFixedWidth(Tokens.CONTROL_HEIGHT)
        self.sidebar_toggle.setAccessibleName("Toggle sidebar")
        header.addWidget(self.sidebar_toggle)

        self.page_title = ly.title("")
        header.addWidget(self.page_title)
        header.addStretch()
        content_layout.addLayout(header)

        self.stack = QStackedWidget()
        for key, _label, _glyph in PAGES:
            page = _PAGE_CLASSES[key](self.calc, self)
            self.pages[key] = page
            self.stack.addWidget(page)
        content_layout.addWidget(self.stack, 1)

        return content

    def create_menu_bar(self):
        """Create application menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('File')

        new_action = QAction('New calculation', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_calculation)
        file_menu.addAction(new_action)

        open_action = QAction('Open project...', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_project)
        file_menu.addAction(open_action)

        save_action = QAction('Save project...', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_project)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        export_action = QAction('Export results...', self)
        export_action.setShortcut('Ctrl+E')
        export_action.triggered.connect(self.export_all_results)
        file_menu.addAction(export_action)

        # View menu - the sidebar can be reached from the keyboard, not only
        # by finding the toggle button.
        view_menu = menubar.addMenu('View')
        self.sidebar_action = QAction('Show sidebar', self)
        self.sidebar_action.setCheckable(True)
        self.sidebar_action.setChecked(True)
        self.sidebar_action.setShortcut(QKeySequence('Ctrl+B'))
        self.sidebar_action.triggered.connect(self.set_sidebar_visible)
        view_menu.addAction(self.sidebar_action)

        # Tools menu
        tools_menu = menubar.addMenu('Tools')

        unit_conv_action = QAction('Unit converter...', self)
        unit_conv_action.triggered.connect(self.open_unit_converter)
        tools_menu.addAction(unit_conv_action)

        mixture_action = QAction('Mixture designer...', self)
        mixture_action.triggered.connect(self.open_mixture_designer)
        tools_menu.addAction(mixture_action)

    # -- Navigation --------------------------------------------------------

    def show_page(self, index: int) -> None:
        """Switch to a page and name it in the header."""
        if not 0 <= index < len(PAGES):
            return
        self.stack.setCurrentIndex(index)
        self.sidebar.set_current(index)
        self.page_title.setText(PAGES[index][1])

    def toggle_sidebar(self) -> None:
        self.set_sidebar_visible(not self.sidebar.isVisible())

    def set_sidebar_visible(self, visible: bool) -> None:
        """Show or hide the navigation rail, restoring its previous width."""
        if visible == self.sidebar.isVisible():
            return
        if not visible:
            self._sidebar_width = max(self.sidebar.width(), Sidebar.MIN_W)
        self.sidebar.setVisible(visible)
        if visible:
            self.splitter.setSizes(
                [self._sidebar_width,
                 max(self.width() - self._sidebar_width, Sidebar.MIN_W)])
        self.sidebar_action.setChecked(visible)
        self.sidebar_toggle.setToolTip(
            "Hide the navigation sidebar (Ctrl+B)" if visible
            else "Show the navigation sidebar (Ctrl+B)")

    # -- Shared busy / status feedback -------------------------------------

    def set_status(self, message: str) -> None:
        """Show a one-line status message."""
        self.statusBar().showMessage(message)

    def set_busy(self, busy: bool, message: str = "") -> None:
        """Show or hide the indeterminate progress indicator.

        The bar appears immediately at its final position - it is never
        animated into place.
        """
        if busy:
            self.progress_bar.setRange(0, 0)   # indeterminate
            self.progress_bar.setVisible(True)
            if message:
                self.set_status(message)
        else:
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)
            if message:
                self.set_status(message)

    # -- File actions ------------------------------------------------------

    def new_calculation(self):
        """Start a new calculation"""
        for page in self.pages.values():
            if hasattr(page, 'clear_data'):
                page.clear_data()
        self.current_mixture = []
        self.set_status('New calculation started')

    def open_project(self):
        """Open a saved project"""
        try:
            filename, _ = QFileDialog.getOpenFileName(
                self, "Open project", "", "JSON Files (*.json)"
            )
            if filename:
                with open(filename, 'r') as f:
                    data = json.load(f)
                self.load_project_data(data)
                self.set_status(f'Project loaded: {filename}')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open project: {str(e)}")

    def save_project(self):
        """Save current project"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Save project", "", "JSON Files (*.json)"
            )
            if filename:
                data = self.get_project_data()
                with open(filename, 'w') as f:
                    json.dump(data, f, indent=4)
                self.set_status(f'Project saved: {filename}')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save project: {str(e)}")

    def export_all_results(self):
        """Export all calculation results"""
        try:
            results = self.get_all_results()
            if not results:
                QMessageBox.information(
                    self, "Nothing to export",
                    "No calculation results yet. Run a calculation first.")
                return
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export results", "", "Excel Files (*.xlsx)"
            )
            if filename:
                if FileIO.export_results(filename, results):
                    self.set_status(f'Results exported: {filename}')
                else:
                    QMessageBox.critical(
                        self, "Export error",
                        f"Failed to export results to {filename}. "
                        f"See the log for details.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export results: {str(e)}")

    # -- Tools -------------------------------------------------------------

    def open_unit_converter(self):
        """Open unit converter dialog"""
        dialog = UnitConverterDialog(self)
        dialog.exec()

    def open_mixture_designer(self):
        """Open mixture designer dialog"""
        dialog = MixtureDialog(self, predefined_mixtures=self.calc.predefined_mixtures,
                               fluids=self.calc.fluids)
        if dialog.exec():
            self.current_mixture = dialog.get_mixture()
            self.update_mixture_display()

    # -- Settings ----------------------------------------------------------

    def save_settings(self):
        """Save application settings"""
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('windowState', self.saveState())
        self.settings.setValue('sidebarVisible', self.sidebar.isVisible())
        self.settings.setValue('sidebarWidth', self._sidebar_width)
        self.settings.setValue('page', self.stack.currentIndex())

    def load_settings(self):
        """Load application settings"""
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        state = self.settings.value('windowState')
        if state:
            self.restoreState(state)

        width = self.settings.value('sidebarWidth', type=int)
        if width:
            self._sidebar_width = max(width, Sidebar.MIN_W)
        page = self.settings.value('page', type=int)
        if page:
            self.show_page(page)
        if self.settings.value('sidebarVisible', True, type=bool) is False:
            self.set_sidebar_visible(False)

    def closeEvent(self, event):
        """Handle window close event"""
        self.save_settings()
        event.accept()

    # -- Project data ------------------------------------------------------

    def load_project_data(self, data):
        """Load project data into the application"""
        try:
            # Load mixture data if present
            if 'mixture' in data:
                self.current_mixture = data['mixture']
                self.update_mixture_display()

            # Load page data if present ('tabs' is the on-disk key from
            # before the sidebar replaced the tab bar; projects saved then
            # still open.)
            for key, page_data in (data.get('tabs') or {}).items():
                page = self.pages.get(key)
                if page is not None and hasattr(page, 'load_tab_data'):
                    page.load_tab_data(page_data)

        except Exception as e:
            QMessageBox.warning(self, "Warning",
                                f"Some project data could not be loaded: {str(e)}")

    def get_project_data(self):
        """Get current project data for saving"""
        data = {}

        # Save mixture data if present
        if self.current_mixture:
            data['mixture'] = self.current_mixture

        data['tabs'] = {
            key: page.get_tab_data()
            for key, page in self.pages.items()
            if hasattr(page, 'get_tab_data')
        }

        return data

    def get_all_results(self):
        """Get all calculation results from all pages"""
        results = {}

        for key, page in self.pages.items():
            if hasattr(page, 'get_results'):
                try:
                    page_results = page.get_results()
                    if page_results is not None:
                        results[key] = page_results
                except Exception:
                    pass

        return results

    def update_mixture_display(self):
        """Update mixture display on the mixture page"""
        mixture_page = self.pages.get('mixture')
        if mixture_page and hasattr(mixture_page, 'update_mixture_display'):
            mixture_page.update_mixture_display(self.current_mixture)
