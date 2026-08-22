import math

from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
                             QGroupBox, QLineEdit, QComboBox, QLabel,
                             QDoubleSpinBox, QPushButton, QTableWidget,
                             QSplitter, QTableWidgetItem, QMessageBox,
                             QFileDialog, QApplication)
from PySide6.QtCore import Qt
import pandas as pd

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

class SinglePointTab(QWidget):
    def __init__(self, calc, parent=None):
        super().__init__(parent)
        self.calc = calc
        self.init_ui()

    def init_ui(self):
        """Create enhanced single point calculation tab"""
        layout = QHBoxLayout(self)

        # Left panel - Input
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Fluid selection with search
        fluid_group = QGroupBox("Fluid Selection")
        fluid_layout = QVBoxLayout(fluid_group)

        self.fluid_search = QLineEdit()
        self.fluid_search.setPlaceholderText("Search fluids...")
        self.fluid_search.textChanged.connect(self.filter_fluids)
        fluid_layout.addWidget(self.fluid_search)

        self.fluid_combo = QComboBox()
        self._all_fluids = list(self.calc.fluids)  # Store full list for filtering
        self.fluid_combo.addItems(self._all_fluids)
        self.fluid_combo.setCurrentText('Water')
        self.fluid_combo.setEditable(True)
        fluid_layout.addWidget(self.fluid_combo)

        left_layout.addWidget(fluid_group)

        # Enhanced input section
        input_group = QGroupBox("State Point Definition")
        input_layout = QGridLayout(input_group)

        # Property 1
        input_layout.addWidget(QLabel("Property 1:"), 0, 0)
        self.prop1_combo = QComboBox()
        self.prop1_combo.addItems(['T', 'P', 'H', 'D', 'S', 'U'])
        input_layout.addWidget(self.prop1_combo, 0, 1)

        self.prop1_value = QDoubleSpinBox()
        self.prop1_value.setRange(-1000, 10000)
        self.prop1_value.setDecimals(6)
        self.prop1_value.setValue(25)
        input_layout.addWidget(self.prop1_value, 0, 2)

        self.prop1_unit = QComboBox()
        self.prop1_unit.addItems(['°C', 'K', '°F'])
        input_layout.addWidget(self.prop1_unit, 0, 3)

        # Property 2
        input_layout.addWidget(QLabel("Property 2:"), 1, 0)
        self.prop2_combo = QComboBox()
        self.prop2_combo.addItems(['T', 'P', 'H', 'D', 'S', 'U'])
        self.prop2_combo.setCurrentText('P')
        input_layout.addWidget(self.prop2_combo, 1, 1)

        self.prop2_value = QDoubleSpinBox()
        self.prop2_value.setRange(0.001, 1000)
        self.prop2_value.setDecimals(6)
        self.prop2_value.setValue(1.01325)
        input_layout.addWidget(self.prop2_value, 1, 2)

        self.prop2_unit = QComboBox()
        self.prop2_unit.addItems(['bara', 'barg', 'Pa', 'psia', 'psig', 'MPa'])
        input_layout.addWidget(self.prop2_unit, 1, 3)

        # Update unit combos when property type changes, and value ranges when
        # the unit changes
        self.prop1_combo.currentTextChanged.connect(self.update_units)
        self.prop2_combo.currentTextChanged.connect(self.update_units)
        self.prop1_unit.currentTextChanged.connect(
            lambda _: self._apply_range(self.prop1_combo, self.prop1_unit, self.prop1_value))
        self.prop2_unit.currentTextChanged.connect(
            lambda _: self._apply_range(self.prop2_combo, self.prop2_unit, self.prop2_value))

        # Initialize units
        self.update_units(is_init=True)

        left_layout.addWidget(input_group)

        # Calculate button
        calc_btn = QPushButton("Calculate Properties")
        calc_btn.clicked.connect(self.calculate_single_point)
        left_layout.addWidget(calc_btn)

        left_layout.addStretch()

        # Right panel - Results
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Results table with enhanced features
        results_group = QGroupBox("Calculation Results")
        results_layout = QVBoxLayout(results_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(['Property', 'Value', 'Unit'])
        header = self.results_table.horizontalHeader()
        if header:
            header.setStretchLastSection(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        results_layout.addWidget(self.results_table)

        # Export options
        export_layout = QHBoxLayout()
        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.clicked.connect(self.export_results)
        export_layout.addWidget(export_csv_btn)

        export_excel_btn = QPushButton("Export Excel")
        export_excel_btn.clicked.connect(self.export_excel)
        export_layout.addWidget(export_excel_btn)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_results)
        export_layout.addWidget(copy_btn)

        results_layout.addLayout(export_layout)
        right_layout.addWidget(results_group)

        # Add panels to splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])

        layout.addWidget(splitter)
        self.setLayout(layout)

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

    def update_units(self, is_init=False):
        """Update unit options based on selected property type"""
        self.prop_to_unit_map = {
            'T': ['°C', 'K', '°F'],
            'P': ['Pa', 'kPa', 'MPa', 'bar', 'bara', 'barg', 'psi', 'psia', 'psig', 'atm'],
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
                self._update_combo(self.prop1_combo, self.prop1_unit, self.prop1_value)
            elif sender == self.prop2_combo:
                self._update_combo(self.prop2_combo, self.prop2_unit, self.prop2_value)

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

    def calculate_single_point(self):
        """Calculate properties for single point"""
        try:
            # Get input values
            fluid = self.fluid_combo.currentText()
            prop1 = self.prop1_combo.currentText()
            prop1_value = self.prop1_value.value()
            prop1_unit = self.prop1_unit.currentText()
            prop2 = self.prop2_combo.currentText()
            prop2_value = self.prop2_value.value()
            prop2_unit = self.prop2_unit.currentText()

            # Validate inputs
            if prop1 == prop2:
                QMessageBox.warning(self, "Input Error", "Property 1 and Property 2 must be different.")
                return

            # Perform calculation (unsupported input pairs raise a clear
            # ValueError from the calculator)
            results = self.calc.calculate_single_point_properties(
                fluid, prop1, prop1_value, prop1_unit, prop2, prop2_value, prop2_unit
            )

            # Display results
            self.display_results(results)

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Failed to calculate properties: {str(e)}")

    def display_results(self, results):
        """Display calculation results in the table"""
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(results))

        for i, (property_name, (value, unit)) in enumerate(results.items()):
            # Property name
            self.results_table.setItem(i, 0, QTableWidgetItem(property_name))

            # Value (formatted)
            if isinstance(value, float) and math.isnan(value):
                val_str = "N/A"
            elif isinstance(value, float) and (abs(value) < 1e-6 or abs(value) > 1e6):
                val_str = f"{value:.4e}"
            elif isinstance(value, float):
                val_str = f"{value:.6g}"
            else:
                val_str = str(value)

            self.results_table.setItem(i, 1, QTableWidgetItem(val_str))

            # Unit
            self.results_table.setItem(i, 2, QTableWidgetItem(unit))

        self.results_table.setSortingEnabled(True)
        # Resize columns to content
        self.results_table.resizeColumnsToContents()

    def _table_rows(self):
        """Current results table contents as a list of [property, value, unit]."""
        data = []
        for row in range(self.results_table.rowCount()):
            property_item = self.results_table.item(row, 0)
            value_item = self.results_table.item(row, 1)
            unit_item = self.results_table.item(row, 2)
            if property_item and value_item and unit_item:
                data.append([property_item.text(), value_item.text(), unit_item.text()])
        return data

    # ── Integration with main window (export / project / clear) ─────────

    def get_results(self):
        """Return current results as a DataFrame, or None if empty."""
        data = self._table_rows()
        if not data:
            return None
        return pd.DataFrame(data, columns=['Property', 'Value', 'Unit'])

    def clear_data(self):
        """Clear results."""
        self.results_table.setRowCount(0)

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

    # ── Export helpers ───────────────────────────────────────────────────

    def export_results(self):
        """Export results to CSV"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Results", "", "CSV Files (*.csv)"
            )
            if filename:
                data = self._table_rows()
                if data:
                    df = pd.DataFrame(data, columns=['Property', 'Value', 'Unit'])
                    df.to_csv(filename, index=False)
                    QMessageBox.information(self, "Export Success", f"Results exported to {filename}")
                else:
                    QMessageBox.information(self, "Nothing to Export", "Calculate properties first.")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export results: {str(e)}")

    def export_excel(self):
        """Export results to Excel"""
        try:
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Results", "", "Excel Files (*.xlsx)"
            )
            if filename:
                data = self._table_rows()
                if data:
                    df = pd.DataFrame(data, columns=['Property', 'Value', 'Unit'])
                    df.to_excel(filename, index=False)
                    QMessageBox.information(self, "Export Success", f"Results exported to {filename}")
                else:
                    QMessageBox.information(self, "Nothing to Export", "Calculate properties first.")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export results: {str(e)}")

    def copy_results(self):
        """Copy results to clipboard"""
        try:
            text = "Property\tValue\tUnit\n"
            for property_name, value, unit in self._table_rows():
                text += f"{property_name}\t{value}\t{unit}\n"

            clipboard = QApplication.clipboard()
            clipboard.setText(text)

            QMessageBox.information(self, "Copy Success", "Results copied to clipboard")

        except Exception as e:
            QMessageBox.critical(self, "Copy Error", f"Failed to copy results: {str(e)}")
