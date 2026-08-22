"""
Tab Manager for ThermoProp application
Handles creation and management of all application tabs
"""

from PySide6.QtWidgets import QTabWidget, QWidget, QVBoxLayout

from .single_point_tab import SinglePointTab
from .mixture_tab import MixtureTab
from .saturation_tab import SaturationTab
from .process_path_tab import ProcessPathTab
from .plotting_tab import PlottingTab

class TabManager:
    """Manages the creation and organization of application tabs"""

    def __init__(self, parent=None, calc=None):
        self.parent = parent
        self.calc = calc
        self.tab_widget = QTabWidget(parent)
        self.tabs = {}
        self._init_tabs()

    def _init_tabs(self):
        """Initialize all application tabs"""
        # Create tab instances
        self.tabs['single_point'] = SinglePointTab(self.calc, self.parent)
        self.tabs['mixture'] = MixtureTab(self.calc, self.parent)
        self.tabs['saturation'] = SaturationTab(self.calc, self.parent)
        self.tabs['process_path'] = ProcessPathTab(self.calc, self.parent)
        self.tabs['plotting'] = PlottingTab(self.calc, self.parent)

        # Add tabs to widget
        self.tab_widget.addTab(self.tabs['single_point'], "Single Point")
        self.tab_widget.addTab(self.tabs['mixture'], "Mixture")
        self.tab_widget.addTab(self.tabs['saturation'], "Saturation")
        self.tab_widget.addTab(self.tabs['process_path'], "Process Path")
        self.tab_widget.addTab(self.tabs['plotting'], "Plotting")

    def get_tab_widget(self):
        """Return the QTabWidget instance"""
        return self.tab_widget

    def get_tab(self, tab_name):
        """Get a specific tab by name"""
        return self.tabs.get(tab_name)

    def clear_all_tabs(self):
        """Clear all tab data"""
        for tab in self.tabs.values():
            if hasattr(tab, 'clear_data'):
                tab.clear_data()

    def get_tab_data(self):
        """Collect serializable input snapshots from all tabs"""
        data = {}
        for name, tab in self.tabs.items():
            if hasattr(tab, 'get_tab_data'):
                data[name] = tab.get_tab_data()
        return data

    def load_tab_data(self, data):
        """Restore tab input snapshots"""
        for name, tab_data in (data or {}).items():
            tab = self.tabs.get(name)
            if tab is not None and hasattr(tab, 'load_tab_data'):
                tab.load_tab_data(tab_data)
