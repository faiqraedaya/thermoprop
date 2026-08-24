import math

import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFileDialog, QLineEdit,
    QMessageBox, QWidget,
)

from . import layout as ly
from .worker import BusyGuard, Worker, host_window

# Per-(property, unit) spinbox limits: (min, max, decimals)
_UNIT_RANGES = {
    ('T', '°C'): (-273.14, 5000.0, 3),
    ('T', 'K'): (0.001, 5273.15, 3),
    ('T', '°F'): (-459.66, 9000.0, 3),
    ('P', 'Pa'): (0.1, 1e10, 1),
    ('P', 'kPa'): (0.0001, 1e7, 4),
    ('P', 'MPa'): (1e-6, 1e4, 6),
    ('P', 'bar'): (1e-6, 1e5, 6),
    ('P', 'bara'): (1e-6, 1e5, 6),
    ('P', 'barg'): (-1.0132, 1e5, 6),
    ('P', 'psi'): (0.0001, 1.5e6, 4),
    ('P', 'psia'): (0.0001, 1.5e6, 4),
    ('P', 'psig'): (-14.695, 1.5e6, 4),
    ('P', 'atm'): (1e-6, 1e5, 6),
    ('H', 'J/kg'): (-1e8, 1e8, 1),
    ('H', 'kJ/kg'): (-1e5, 1e5, 4),
    ('H', 'MJ/kg'): (-100.0, 100.0, 6),
    ('H', 'BTU/lb'): (-50000.0, 50000.0, 4),
    ('U', 'J/kg'): (-1e8, 1e8, 1),
    ('U', 'kJ/kg'): (-1e5, 1e5, 4),
    ('U', 'MJ/kg'): (-100.0, 100.0, 6),
    ('U', 'BTU/lb'): (-50000.0, 50000.0, 4),
    ('D', 'kg/m³'): (0.0001, 1e5, 4),
    ('D', 'g/cm³'): (1e-6, 100.0, 6),
    ('D', 'lb/ft³'): (0.0001, 7000.0, 4),
    ('D', 'kg/L'): (1e-6, 100.0, 6),
    ('S', 'J/kg/K'): (-1e6, 1e6, 2),
    ('S', 'kJ/kg/K'): (-1000.0, 1000.0, 5),
}

_PROPERTY_NAMES = {
    'T': 'Temperature',
    'P': 'Pressure',
    'H': 'Enthalpy',
    'D': 'Density',
    'S': 'Entropy',
    'U': 'Internal energy',
}


class SinglePointTab(QWidget):
    def __init__(self, calc, parent=None):
        super().__init__(parent)
        self.calc = calc
        self._worker = None
        self.init_ui()

    def init_ui(self):
        """Single point calculation tab: inputs on the left, results on the right."""
        layout = ly.hbox(self, spacing=0)

        layout.addWidget(ly.splitter(
            self._build_input_panel(),
            self._build_results_panel(),
            sizes=[440, 760], stretch=[0, 1]))

    # -- Input panel ------------------------------------------------------

    def _build_input_panel(self) -> QWidget:
        panel, panel_layout = ly.panel()
        panel.setMinimumWidth(360)

        # Fluid: a filter above the list, so a long fluid list stays usable
        fluid_section = ly.vbox()
        fluid_section.addWidget(ly.heading("Fluid"))

        self.fluid_search = QLineEdit()
        self.fluid_search.setPlaceholderText("Filter the fluid list")
        self.fluid_search.setToolTip(
            "Narrows the list below. Clearing it restores every fluid.")
        self.fluid_search.textChanged.connect(self.filter_fluids)
        ly.value_field(self.fluid_search)
        fluid_section.addWidget(self.fluid_search)

        self.fluid_combo = QComboBox()
        self._all_fluids = list(self.calc.fluids)  # full list, for filtering
        self.fluid_combo.addItems(self._all_fluids)
        self.fluid_combo.setCurrentText('Water')
        self.fluid_combo.setEditable(True)
        ly.choice_field(self.fluid_combo)
        fluid_section.addWidget(self.fluid_combo)
        panel_layout.addLayout(fluid_section)

        # State point: two known properties fix the state
        state_section = ly.vbox()
        state_section.addWidget(ly.heading("State point"))
        state_section.addWidget(ly.caption(
            "Two independent properties fix the state. They must differ."))

        state_grid = ly.grid()
        state_grid.addWidget(ly.caption("Property"), 0, 1)
        state_grid.addWidget(ly.caption("Value"), 0, 2)
        state_grid.addWidget(ly.caption("Unit"), 0, 3)

        state_grid.addWidget(ly.field_label("Property 1"), 1, 0)
        self.prop1_combo = self._property_combo('T')
        state_grid.addWidget(self.prop1_combo, 1, 1)
        self.prop1_value = self._value_spin(25.0, -1000, 10000)
        state_grid.addWidget(self.prop1_value, 1, 2)
        self.prop1_unit = ly.choice_field(QComboBox(), min_width=88)
        self.prop1_unit.addItems(['°C', 'K', '°F'])
        state_grid.addWidget(self.prop1_unit, 1, 3)

        state_grid.addWidget(ly.field_label("Property 2"), 2, 0)
        self.prop2_combo = self._property_combo('P')
        state_grid.addWidget(self.prop2_combo, 2, 1)
        self.prop2_value = self._value_spin(1.01325, 0.001, 1000)
        state_grid.addWidget(self.prop2_value, 2, 2)
        self.prop2_unit = ly.choice_field(QComboBox(), min_width=88)
        self.prop2_unit.addItems(['bara', 'barg', 'Pa', 'psia', 'psig', 'MPa'])
        state_grid.addWidget(self.prop2_unit, 2, 3)

        state_grid.setColumnStretch(2, 1)
        state_section.addLayout(state_grid)
        panel_layout.addLayout(state_section)

        # Units follow the property type; ranges follow the unit
        self.prop1_combo.currentTextChanged.connect(self.update_units)
        self.prop2_combo.currentTextChanged.connect(self.update_units)
        self.prop1_unit.currentTextChanged.connect(
            lambda _: self._apply_range(self.prop1_combo, self.prop1_unit,
                                        self.prop1_value))
        self.prop2_unit.currentTextChanged.connect(
            lambda _: self._apply_range(self.prop2_combo, self.prop2_unit,
                                        self.prop2_value))
        self.update_units(is_init=True)

        # One action, so one primary button
        self.calc_btn = ly.button("Calculate properties", variant="primary",
                                  on_click=self.calculate_single_point)
        panel_layout.addLayout(ly.action_row(self.calc_btn))

        self.input_status = ly.status_label()
        panel_layout.addWidget(self.input_status)

        panel_layout.addStretch()
        return panel

    def _property_combo(self, initial: str) -> QComboBox:
        combo = QComboBox()
        for key, name in _PROPERTY_NAMES.items():
            combo.addItem(key)
            combo.setItemData(combo.count() - 1, name, 3)   # Qt.ToolTipRole
        combo.setCurrentText(initial)
        return ly.choice_field(combo, min_width=72)

    @staticmethod
    def _value_spin(value: float, lo: float, hi: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(lo, hi)
        spin.setDecimals(6)
        spin.setValue(value)
        return ly.value_field(spin)

    # -- Results panel ----------------------------------------------------

    def _build_results_panel(self) -> QWidget:
        panel, panel_layout = ly.panel()
        panel.setMinimumWidth(360)

        panel_layout.addWidget(ly.heading("Results"))

        self.results_table = ly.results_table(
            ['Property', 'Value', 'Unit'],
            empty_text="Calculated properties appear here.\n"
                       "Pick a fluid and two state properties, then choose "
                       "Calculate properties.",
            sortable=True,
        )
        panel_layout.addWidget(self.results_table, 1)

        # An export row has no single dominant action, so no primary button
        export_row = ly.hbox()
        export_row.addWidget(ly.button("Export CSV", on_click=self.export_results))
        export_row.addWidget(ly.button("Export Excel", on_click=self.export_excel))
        export_row.addWidget(ly.button("Copy to clipboard",
                                       on_click=self.copy_results))
        export_row.addStretch()
        panel_layout.addLayout(export_row)
        return panel

    # -- Input behaviour --------------------------------------------------

    def filter_fluids(self, text):
        """Filter fluids based on search text"""
        current_text = self.fluid_combo.currentText()
        filtered = [f for f in self._all_fluids if text.lower() in f.lower()]
        self.fluid_combo.blockSignals(True)
        self.fluid_combo.clear()
        self.fluid_combo.addItems(filtered)
        # Try to restore the current selection if possible
        if current_text in filtered:
            self.fluid_combo.setCurrentText(current_text)
        elif filtered:
            self.fluid_combo.setCurrentIndex(0)
        self.fluid_combo.blockSignals(False)

        if text and not filtered:
            ly.set_status(self.input_status,
                          f"No fluid matches '{text}'.", "warning")
        elif self.input_status.property("role") == "warning":
            ly.set_status(self.input_status, "")

    def update_units(self, is_init=False):
        """Update unit options based on selected property type"""
        self.prop_to_unit_map = {
            'T': ['°C', 'K', '°F'],
            'P': ['Pa', 'kPa', 'MPa', 'bar', 'bara', 'barg', 'psi', 'psia',
                  'psig', 'atm'],
            'H': ['J/kg', 'kJ/kg', 'MJ/kg', 'BTU/lb'],
            'D': ['kg/m³', 'g/cm³', 'lb/ft³', 'kg/L'],
            'S': ['J/kg/K', 'kJ/kg/K'],
            'U': ['J/kg', 'kJ/kg', 'MJ/kg', 'BTU/lb']
        }

        if is_init:
            # Initial setup for both
            self._update_combo(self.prop1_combo, self.prop1_unit, self.prop1_value)
            self._update_combo(self.prop2_combo, self.prop2_unit, self.prop2_value)
        else:
            sender = self.sender()
            if sender == self.prop1_combo:
                self._update_combo(self.prop1_combo, self.prop1_unit,
                                   self.prop1_value)
            elif sender == self.prop2_combo:
                self._update_combo(self.prop2_combo, self.prop2_unit,
                                   self.prop2_value)

    def _update_combo(self, prop_combo, unit_combo, value_spin):
        """Helper to update a single unit combo box and the value range"""
        prop = prop_combo.currentText()
        units = self.prop_to_unit_map.get(prop, [])

        current_unit = unit_combo.currentText()
        unit_combo.blockSignals(True)
        unit_combo.clear()
        if units:
            unit_combo.addItems(units)
            if current_unit in units:
                unit_combo.setCurrentText(current_unit)
            else:
                unit_combo.setCurrentIndex(0)
        unit_combo.blockSignals(False)
        self._apply_range(prop_combo, unit_combo, value_spin)

    @staticmethod
    def _apply_range(prop_combo, unit_combo, value_spin):
        """Set spinbox limits appropriate for the selected property + unit."""
        prop = prop_combo.currentText()
        unit = unit_combo.currentText()
        if not unit:
            return
        lo, hi, decimals = _UNIT_RANGES.get((prop, unit), (-1e10, 1e10, 6))
        value_spin.setDecimals(decimals)
        value_spin.setRange(lo, hi)
        value_spin.setToolTip(
            f"{_PROPERTY_NAMES.get(prop, prop)} in {unit}, "
            f"between {lo:g} and {hi:g}")

    # -- Calculation ------------------------------------------------------

    def calculate_single_point(self):
        """Calculate properties for single point"""
        if self._worker is not None and self._worker.isRunning():
            return

        fluid = self.fluid_combo.currentText()
        prop1 = self.prop1_combo.currentText()
        prop2 = self.prop2_combo.currentText()

        if prop1 == prop2:
            ly.set_status(
                self.input_status,
                f"Property 1 and property 2 are both "
                f"{_PROPERTY_NAMES.get(prop1, prop1).lower()}. "
                f"Two different properties are needed to fix the state.",
                "error")
            return
        ly.set_status(self.input_status, "")

        args = (fluid, prop1, self.prop1_value.value(),
                self.prop1_unit.currentText(), prop2, self.prop2_value.value(),
                self.prop2_unit.currentText())

        self._busy = BusyGuard(self, [self.calc_btn],
                               f"Calculating {fluid} properties...")
        self._busy.start()

        self._worker = Worker(
            self.calc.calculate_single_point_properties, *args)
        self._worker.done.connect(self._on_results)
        self._worker.failed.connect(self._on_failure)
        self._worker.start()

    def _on_results(self, results):
        self._busy.stop(f"{len(results)} properties calculated")
        self.display_results(results)

    def _on_failure(self, message):
        self._busy.stop("Calculation failed")
        ly.set_status(self.input_status,
                      f"Could not calculate: {message}", "error")

    def display_results(self, results):
        """Display calculation results in the table"""
        rows = [[name, self._format(value), unit]
                for name, (value, unit) in results.items()]
        ly.fill_table(self.results_table, rows, numeric_columns=(1,))

    @staticmethod
    def _format(value) -> str:
        """Format a value so magnitude stays readable at any scale."""
        if isinstance(value, float) and math.isnan(value):
            return "N/A"
        if isinstance(value, float) and (abs(value) < 1e-6 or abs(value) > 1e6):
            return f"{value:.4e}"
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    def _table_rows(self):
        """Current results table contents as a list of [property, value, unit]."""
        return ly.table_rows(self.results_table)

    # -- Integration with main window (export / project / clear) ----------

    def get_results(self):
        """Return current results as a DataFrame, or None if empty."""
        data = self._table_rows()
        if not data:
            return None
        return pd.DataFrame(data, columns=['Property', 'Value', 'Unit'])

    def clear_data(self):
        """Clear results."""
        self.results_table.setRowCount(0)
        ly.set_status(self.input_status, "")

    def get_tab_data(self):
        """Serializable snapshot of the tab's inputs."""
        return {
            'fluid': self.fluid_combo.currentText(),
            'prop1': self.prop1_combo.currentText(),
            'prop1_value': self.prop1_value.value(),
            'prop1_unit': self.prop1_unit.currentText(),
            'prop2': self.prop2_combo.currentText(),
            'prop2_value': self.prop2_value.value(),
            'prop2_unit': self.prop2_unit.currentText(),
        }

    def load_tab_data(self, data):
        """Restore the tab's inputs from a snapshot."""
        if 'fluid' in data:
            self.fluid_combo.setCurrentText(data['fluid'])
        if 'prop1' in data:
            self.prop1_combo.setCurrentText(data['prop1'])
        if 'prop1_unit' in data:
            self.prop1_unit.setCurrentText(data['prop1_unit'])
        if 'prop1_value' in data:
            self.prop1_value.setValue(data['prop1_value'])
        if 'prop2' in data:
            self.prop2_combo.setCurrentText(data['prop2'])
        if 'prop2_unit' in data:
            self.prop2_unit.setCurrentText(data['prop2_unit'])
        if 'prop2_value' in data:
            self.prop2_value.setValue(data['prop2_value'])

    # -- Export helpers ---------------------------------------------------

    def _export(self, caption: str, file_filter: str, writer):
        data = self._table_rows()
        if not data:
            ly.set_status(self.input_status,
                          "Nothing to export yet. Calculate properties first.",
                          "warning")
            return
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, caption, "", file_filter)
            if not filename:
                return
            writer(pd.DataFrame(data, columns=['Property', 'Value', 'Unit']),
                   filename)
            window = host_window(self)
            if window is not None:
                window.set_status(f"Results exported: {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Export error",
                                 f"Failed to export results: {str(e)}")

    def export_results(self):
        """Export results to CSV"""
        self._export("Export results", "CSV Files (*.csv)",
                     lambda df, path: df.to_csv(path, index=False))

    def export_excel(self):
        """Export results to Excel"""
        self._export("Export results", "Excel Files (*.xlsx)",
                     lambda df, path: df.to_excel(path, index=False))

    def copy_results(self):
        """Copy results to clipboard"""
        data = self._table_rows()
        if not data:
            ly.set_status(self.input_status,
                          "Nothing to copy yet. Calculate properties first.",
                          "warning")
            return
        try:
            text = "Property\tValue\tUnit\n"
            for property_name, value, unit in data:
                text += f"{property_name}\t{value}\t{unit}\n"
            QApplication.clipboard().setText(text)
            window = host_window(self)
            if window is not None:
                window.set_status(f"{len(data)} rows copied to clipboard")
        except Exception as e:
            QMessageBox.critical(self, "Copy error",
                                 f"Failed to copy results: {str(e)}")
