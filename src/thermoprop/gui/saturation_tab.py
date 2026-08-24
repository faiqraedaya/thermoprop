import logging
import math

import pandas as pd
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QWidget

from .plot_canvas import PlotCanvas
from ..core.sweeps import saturation_sweep
from . import layout as ly
from .theme import Tokens
from .worker import BusyGuard, Worker

logger = logging.getLogger(__name__)

_COLUMNS = ['Property', 'Value', 'Unit']

_UNITS_FOR = {
    'Temperature': ['°C', 'K', '°F'],
    'Pressure': ['bar', 'kPa', 'MPa', 'atm', 'psi'],
}


class SaturationTab(QWidget):
    def __init__(self, calc, parent=None):
        super().__init__(parent)
        self.calc = calc
        self._worker = None
        self.init_ui()

    def init_ui(self):
        """Saturation tab: one input row, then the table beside its curve."""
        layout = ly.vbox(self, spacing=Tokens.SPACING_GROUP)

        layout.addLayout(self._build_input_section())

        table_panel, table_layout = ly.panel(spacing=Tokens.SPACING_ROW)
        table_panel.setMinimumWidth(320)
        table_layout.addWidget(ly.heading("Saturation properties"))
        self.sat_results_table = ly.results_table(
            _COLUMNS,
            empty_text="Saturated liquid and vapour properties appear here.\n"
                       "Pick a fluid and a known temperature or pressure, "
                       "then choose Calculate.",
        )
        table_layout.addWidget(self.sat_results_table)

        plot_panel, plot_layout = ly.panel(spacing=Tokens.SPACING_ROW)
        plot_panel.setMinimumWidth(360)
        plot_layout.addWidget(ly.heading("Saturation curve"))
        self.sat_plot_canvas = PlotCanvas(
            plot_panel, width=8, height=6,
            empty_text="The saturation curve around your state point "
                       "is drawn here.")
        plot_layout.addWidget(self.sat_plot_canvas)

        layout.addWidget(ly.splitter(table_panel, plot_panel,
                                     sizes=[460, 940], stretch=[0, 1]), 1)

    def _build_input_section(self):
        section = ly.vbox()
        section.addWidget(ly.heading("Saturation state"))

        input_grid = ly.grid()
        input_grid.addWidget(ly.field_label("Fluid"), 0, 0)
        self.sat_fluid_combo = ly.choice_field(QComboBox(), min_width=200)
        self.sat_fluid_combo.addItems(self.calc.fluids)
        self.sat_fluid_combo.setCurrentText('Water')
        input_grid.addWidget(self.sat_fluid_combo, 0, 1)

        input_grid.addWidget(ly.field_label("Known property"), 0, 2)
        self.sat_type_combo = ly.choice_field(QComboBox(), min_width=140)
        self.sat_type_combo.addItems(list(_UNITS_FOR))
        self.sat_type_combo.currentTextChanged.connect(self.update_sat_units)
        input_grid.addWidget(self.sat_type_combo, 0, 3)

        input_grid.addWidget(ly.field_label("Value"), 1, 0)
        self.sat_value = QDoubleSpinBox()
        self.sat_value.setRange(-273.14, 5000)
        self.sat_value.setDecimals(4)
        self.sat_value.setValue(100)
        ly.value_field(self.sat_value)
        input_grid.addWidget(self.sat_value, 1, 1)

        input_grid.addWidget(ly.field_label("Unit"), 1, 2)
        self.sat_unit = ly.choice_field(QComboBox(), min_width=140)
        self.sat_unit.addItems(_UNITS_FOR['Temperature'])
        input_grid.addWidget(self.sat_unit, 1, 3)

        input_grid.setColumnStretch(1, 1)
        input_grid.setColumnStretch(3, 1)
        section.addLayout(input_grid)

        self.calc_btn = ly.button("Calculate", variant="primary",
                                  on_click=self.calculate_saturation)
        section.addLayout(ly.action_row(self.calc_btn))

        self.status = ly.status_label()
        section.addWidget(self.status)
        return section

    def update_sat_units(self):
        """Update saturation units based on input type"""
        sat_type = self.sat_type_combo.currentText()
        self.sat_unit.clear()
        self.sat_unit.addItems(_UNITS_FOR.get(sat_type, []))

        if sat_type == 'Temperature':
            self.sat_value.setRange(-273.14, 5000)
            self.sat_value.setValue(100)
        else:  # Pressure
            self.sat_value.setRange(0.0001, 100000)
            self.sat_value.setValue(1.01325)

    # -- Calculation ------------------------------------------------------

    def calculate_saturation(self):
        """Calculate saturation properties and the curve around them."""
        if self._worker is not None and self._worker.isRunning():
            return

        fluid = self.sat_fluid_combo.currentText()
        sat_type = self.sat_type_combo.currentText()
        sat_value = self.sat_value.value()
        sat_unit = self.sat_unit.currentText()
        sat_type_char = 'T' if sat_type == 'Temperature' else 'P'

        ly.set_status(self.status, "")

        self._busy = BusyGuard(
            self, [self.calc_btn, self.sat_fluid_combo, self.sat_type_combo,
                   self.sat_value, self.sat_unit],
            f"Calculating {fluid} saturation properties...")
        self._busy.start()

        self._worker = Worker(self._compute, fluid, sat_type_char,
                              sat_value, sat_unit)
        self._worker.done.connect(self._on_results)
        self._worker.failed.connect(self._on_failure)
        self._worker.start()

    def _compute(self, fluid, sat_type, sat_value, sat_unit):
        """Off-thread work: the properties, plus the sweep the plot needs."""
        results = self.calc.calculate_saturation_properties(
            fluid, sat_type, sat_value, sat_unit)

        sweep = None
        try:
            if sat_type == 'T':
                T_center = self.calc._convert_to_si(sat_value, sat_unit, 'T')
            else:
                from CoolProp.CoolProp import PropsSI
                P_center = self.calc._convert_to_si(sat_value, sat_unit, 'P')
                T_center = PropsSI('T', 'P', P_center, 'Q', 0, fluid)
            sweep = saturation_sweep(fluid, 50,
                                     t_min=T_center * 0.8, t_max=T_center * 1.2)
        except Exception as e:
            # The numbers are the deliverable; a missing curve must not lose them
            logger.warning("Failed to build saturation sweep: %s", e)

        return results, sweep, fluid, sat_type

    def _on_results(self, payload):
        results, sweep, fluid, sat_type = payload
        self._busy.stop(f"{len(results)} saturation properties calculated")
        self.display_saturation_results(results)
        if sweep is None:
            self.sat_plot_canvas.show_message(
                f"No saturation curve available for {fluid} around this "
                f"state. The property values are still shown.")
            return
        self.sat_plot_canvas.plot_saturation_curve(sweep, fluid, sat_type)

    def _on_failure(self, message):
        self._busy.stop("Saturation calculation failed")
        ly.set_status(self.status,
                      f"Could not calculate saturation properties: {message}",
                      "error")

    def display_saturation_results(self, results):
        """Display saturation calculation results"""
        rows = [[name, self._format(value), unit]
                for name, (value, unit) in results.items()]
        ly.fill_table(self.sat_results_table, rows, numeric_columns=(1,))

    @staticmethod
    def _format(value) -> str:
        """Format a value so magnitude stays readable at any scale."""
        if isinstance(value, float) and math.isnan(value):
            return "N/A"
        if isinstance(value, float) and value != 0 and (
                abs(value) < 1e-6 or abs(value) > 1e6):
            return f"{value:.4e}"
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    # -- Integration with main window (export / project / clear) ----------

    def get_results(self):
        """Return current saturation results as a DataFrame, or None if empty."""
        rows = ly.table_rows(self.sat_results_table)
        if not rows:
            return None
        return pd.DataFrame(rows, columns=_COLUMNS)

    def clear_data(self):
        """Clear results and plot."""
        self.sat_results_table.setRowCount(0)
        self.sat_plot_canvas.clear()
        ly.set_status(self.status, "")

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
