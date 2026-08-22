import logging

import numpy as np
import pandas as pd
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QGroupBox,
                             QComboBox, QLabel, QDoubleSpinBox, QPushButton,
                             QTableWidget, QSplitter, QTableWidgetItem,
                             QMessageBox)
from PySide6.QtCore import Qt

from ..core.plot_canvas import PlotCanvas
from ..core.sweeps import saturation_sweep

logger = logging.getLogger(__name__)

class SaturationTab(QWidget):
    def __init__(self, calc, parent=None):
        super().__init__(parent)
        self.calc = calc
        self.init_ui()

    def init_ui(self):
        """Create enhanced saturation properties tab"""
        layout = QVBoxLayout(self)

        # Input section with multiple options
        input_group = QGroupBox("Saturation Calculation")
        input_layout = QGridLayout(input_group)

        # Fluid selection
        input_layout.addWidget(QLabel("Fluid:"), 0, 0)
        self.sat_fluid_combo = QComboBox()
        self.sat_fluid_combo.addItems(self.calc.fluids)
        self.sat_fluid_combo.setCurrentText('Water')
        input_layout.addWidget(self.sat_fluid_combo, 0, 1)

        # Input parameter
        input_layout.addWidget(QLabel("Given:"), 2, 0)
        self.sat_type_combo = QComboBox()
        self.sat_type_combo.addItems(['Temperature', 'Pressure'])
        input_layout.addWidget(self.sat_type_combo, 2, 1)

        # Value and unit
        self.sat_value = QDoubleSpinBox()
        self.sat_value.setRange(-273.14, 5000)
        self.sat_value.setDecimals(4)
        self.sat_value.setValue(100)
        input_layout.addWidget(self.sat_value, 2, 2)

        self.sat_unit = QComboBox()
        self.sat_unit.addItems(['°C', 'K', '°F'])
        input_layout.addWidget(self.sat_unit, 2, 3)

        # Update units when type changes
        self.sat_type_combo.currentTextChanged.connect(self.update_sat_units)

        layout.addWidget(input_group)

        # Calculate button
        sat_calc_btn = QPushButton("Calculate")
        sat_calc_btn.clicked.connect(self.calculate_saturation)
        layout.addWidget(sat_calc_btn)

        # Results in splitter
        results_splitter = QSplitter(Qt.Horizontal)

        # Table results
        self.sat_results_table = QTableWidget()
        self.sat_results_table.setColumnCount(3)
        self.sat_results_table.setHorizontalHeaderLabels(['Property', 'Value', 'Unit'])
        results_splitter.addWidget(self.sat_results_table)

        # Plot canvas for saturation curve
        self.sat_plot_canvas = PlotCanvas(self, width=8, height=6)
        results_splitter.addWidget(self.sat_plot_canvas)

        layout.addWidget(results_splitter)

        self.setLayout(layout)

    def update_sat_units(self):
        """Update saturation units based on input type"""
        sat_type = self.sat_type_combo.currentText()
        self.sat_unit.clear()

        if sat_type == 'Temperature':
            self.sat_unit.addItems(['°C', 'K', '°F'])
            self.sat_value.setRange(-273.14, 5000)
            self.sat_value.setValue(100)
        else:  # Pressure
            self.sat_unit.addItems(['bar', 'kPa', 'MPa', 'atm', 'psi'])
            self.sat_value.setRange(0.0001, 100000)
            self.sat_value.setValue(1.01325)

    def calculate_saturation(self):
        """Calculate saturation properties"""
        try:
            # Get input values
            fluid = self.sat_fluid_combo.currentText()
            sat_type = self.sat_type_combo.currentText()
            sat_value = self.sat_value.value()
            sat_unit = self.sat_unit.currentText()

            # Convert sat_type to single character
            if sat_type == 'Temperature':
                sat_type_char = 'T'
            else:
                sat_type_char = 'P'

            # Perform calculation
            results = self.calc.calculate_saturation_properties(
                fluid, sat_type_char, sat_value, sat_unit
            )

            # Display results
            self.display_saturation_results(results)

            # Update plot
            self.update_saturation_plot(fluid, sat_type_char, sat_value, sat_unit)

        except Exception as e:
            QMessageBox.critical(self, "Calculation Error",
                                 f"Failed to calculate saturation properties: {str(e)}")

    def display_saturation_results(self, results):
        """Display saturation calculation results"""
        self.sat_results_table.setRowCount(len(results))

        for i, (property_name, (value, unit)) in enumerate(results.items()):
            # Property name
            self.sat_results_table.setItem(i, 0, QTableWidgetItem(property_name))

            # Value (formatted)
            if isinstance(value, float) and np.isnan(value):
                formatted_value = "N/A"
            elif isinstance(value, float) and (abs(value) < 1e-6 or abs(value) > 1e6):
                formatted_value = f"{value:.4e}"
            elif isinstance(value, float):
                formatted_value = f"{value:.6g}"
            else:
                formatted_value = str(value)
            self.sat_results_table.setItem(i, 1, QTableWidgetItem(formatted_value))

            # Unit
            self.sat_results_table.setItem(i, 2, QTableWidgetItem(unit))

        # Resize columns to content
        self.sat_results_table.resizeColumnsToContents()

    def update_saturation_plot(self, fluid, sat_type, sat_value, sat_unit):
        """Update saturation curve plot around the requested state"""
        try:
            # Center the plotted window on the requested saturation point
            if sat_type == 'T':
                T_center = self.calc._convert_to_si(sat_value, sat_unit, 'T')
            else:
                P_center = self.calc._convert_to_si(sat_value, sat_unit, 'P')
                from CoolProp.CoolProp import PropsSI
                T_center = PropsSI('T', 'P', P_center, 'Q', 0, fluid)

            sat = saturation_sweep(fluid, 50,
                                   t_min=T_center * 0.8, t_max=T_center * 1.2)

            fig = self.sat_plot_canvas.fig
            fig.clear()
            ax = fig.add_subplot(111)
            self.sat_plot_canvas.axes = ax

            if sat_type == 'T':
                ax.semilogy(sat['T'], sat['P'], 'b-', label=f'{fluid} Saturation')
                ax.set_xlabel('Temperature (K)')
                ax.set_ylabel('Saturation Pressure (Pa)')
                ax.set_title(f'{fluid} Saturation Curve (P vs T)')
            else:
                ax.plot(sat['P'], sat['T'], 'r-', label=f'{fluid} Saturation')
                ax.set_xlabel('Saturation Pressure (Pa)')
                ax.set_ylabel('Temperature (K)')
                ax.set_title(f'{fluid} Saturation Curve (T vs P)')
            ax.legend()
            ax.grid(True)
            self.sat_plot_canvas.draw()
        except Exception as e:
            logger.warning("Failed to update saturation plot: %s", e)
            # Continue without plot update

    # ── Integration with main window (export / project / clear) ─────────

    def get_results(self):
        """Return current saturation results as a DataFrame, or None if empty."""
        rows = []
        for row in range(self.sat_results_table.rowCount()):
            items = [self.sat_results_table.item(row, col) for col in range(3)]
            if all(items):
                rows.append([item.text() for item in items])
        if not rows:
            return None
        return pd.DataFrame(rows, columns=['Property', 'Value', 'Unit'])

    def clear_data(self):
        """Clear results and plot."""
        self.sat_results_table.setRowCount(0)
        self.sat_plot_canvas.clear()

    def get_tab_data(self):
        """Serializable snapshot of the tab's inputs."""
        return {
            'fluid': self.sat_fluid_combo.currentText(),
            'given': self.sat_type_combo.currentText(),
            'value': self.sat_value.value(),
            'unit': self.sat_unit.currentText(),
        }

    def load_tab_data(self, data):
        """Restore the tab's inputs from a snapshot."""
        if 'fluid' in data:
            self.sat_fluid_combo.setCurrentText(data['fluid'])
        if 'given' in data:
            self.sat_type_combo.setCurrentText(data['given'])
        if 'unit' in data:
            self.sat_unit.setCurrentText(data['unit'])
        if 'value' in data:
            self.sat_value.setValue(data['value'])
