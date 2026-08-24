import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QSpinBox, QTabWidget, QTextEdit, QWidget,
)

from .plot_canvas import PlotCanvas
from . import layout as ly
from .theme import Tokens
from .worker import BusyGuard, Worker

# Maps process type -> (final_value label text, unit string, is_pressure)
_PROCESS_FINAL_META = {
    'Isobaric':    ("Final temperature", "°C",  False),
    'Isochoric':   ("Final temperature", "°C",  False),
    'Isothermal':  ("Final pressure",    "bar", True),
    'Isenthalpic': ("Final pressure",    "bar", True),
    'Isentropic':  ("Final pressure",    "bar", True),
    'Polytropic':  ("Final pressure",    "bar", True),
}

# Maps SI result keys -> (display header with unit, conversion from SI)
_DISPLAY_COLUMNS = {
    'Temperature':     ('Temperature (°C)',     lambda v: v - 273.15),
    'Pressure':        ('Pressure (bar)',       lambda v: v / 1e5),
    'Enthalpy':        ('Enthalpy (kJ/kg)',     lambda v: v / 1000),
    'Entropy':         ('Entropy (kJ/kg·K)',    lambda v: v / 1000),
    'Density':         ('Density (kg/m³)',      lambda v: v),
    'Internal Energy': ('Internal Energy (kJ/kg)', lambda v: v / 1000),
    'Quality':         ('Quality (-)',          lambda v: v),
    'Phase':           ('Phase',                None),
}


class ProcessPathTab(QWidget):
    def __init__(self, calc, parent=None):
        super().__init__(parent)
        self.calc = calc
        self._worker = None
        self.init_ui()

    def init_ui(self):
        """Process path tab: the path definition, then its three result views."""
        layout = ly.vbox(self, spacing=Tokens.SPACING_GROUP)
        layout.addLayout(self._build_input_section())
        layout.addWidget(self._build_results_section(), 1)

        # Initialise the dynamic label and the polytropic control's visibility
        self._update_final_label(self.process_type.currentText())

    # -- Input ------------------------------------------------------------

    def _build_input_section(self):
        section = ly.vbox()
        section.addWidget(ly.heading("Process path"))

        input_grid = ly.grid()

        input_grid.addWidget(ly.field_label("Fluid"), 0, 0)
        self.proc_fluid_combo = ly.choice_field(QComboBox(), min_width=200)
        self.proc_fluid_combo.addItems(self.calc.fluids)
        self.proc_fluid_combo.setCurrentText('Water')
        input_grid.addWidget(self.proc_fluid_combo, 0, 1)

        input_grid.addWidget(ly.field_label("Process"), 0, 2)
        self.process_type = ly.choice_field(QComboBox(), min_width=140)
        self.process_type.addItems(list(_PROCESS_FINAL_META.keys()))
        self.process_type.currentTextChanged.connect(self._update_final_label)
        input_grid.addWidget(self.process_type, 0, 3)

        input_grid.addWidget(ly.field_label("Initial temperature (°C)"), 1, 0)
        self.init_temp = QDoubleSpinBox()
        self.init_temp.setRange(-273.14, 2000)
        self.init_temp.setDecimals(3)
        self.init_temp.setValue(25)
        ly.value_field(self.init_temp)
        input_grid.addWidget(self.init_temp, 1, 1)

        input_grid.addWidget(ly.field_label("Initial pressure (bar)"), 1, 2)
        self.init_pres = QDoubleSpinBox()
        self.init_pres.setRange(0.001, 10000)
        self.init_pres.setDecimals(5)
        self.init_pres.setValue(1.01325)
        ly.value_field(self.init_pres)
        input_grid.addWidget(self.init_pres, 1, 3)

        self.final_label = ly.field_label("Final temperature (°C)")
        input_grid.addWidget(self.final_label, 2, 0)
        self.final_condition = QDoubleSpinBox()
        self.final_condition.setRange(-273.14, 10000)
        self.final_condition.setDecimals(4)
        self.final_condition.setValue(100)
        ly.value_field(self.final_condition)
        input_grid.addWidget(self.final_condition, 2, 1)

        input_grid.addWidget(ly.field_label("Points along the path"), 2, 2)
        self.num_points = QSpinBox()
        self.num_points.setRange(10, 1000)
        self.num_points.setValue(50)
        self.num_points.setToolTip(
            "How many states are evaluated between the initial and final "
            "conditions.")
        ly.value_field(self.num_points)
        input_grid.addWidget(self.num_points, 2, 3)

        # Polytropic exponent: only meaningful for a polytropic path
        self.poly_n_label = ly.field_label("Polytropic exponent n")
        input_grid.addWidget(self.poly_n_label, 3, 0)
        self.poly_n = QDoubleSpinBox()
        self.poly_n.setRange(0.01, 10.0)
        self.poly_n.setSingleStep(0.05)
        self.poly_n.setValue(1.3)
        self.poly_n.setDecimals(3)
        self.poly_n.setToolTip("Exponent in p·v^n = constant.")
        ly.value_field(self.poly_n)
        input_grid.addWidget(self.poly_n, 3, 1)

        input_grid.setColumnStretch(1, 1)
        input_grid.setColumnStretch(3, 1)
        section.addLayout(input_grid)

        self.proc_calc_btn = ly.button("Simulate process", variant="primary",
                                       on_click=self.simulate_process)
        section.addLayout(ly.action_row(self.proc_calc_btn))

        self.status = ly.status_label()
        section.addWidget(self.status)
        return section

    # -- Results ----------------------------------------------------------

    def _build_results_section(self) -> QWidget:
        # Inner tabs: the outer tab pane already draws the boundary, so this
        # one is marked "inner" and drops its own border.
        results_tabs = QTabWidget()
        results_tabs.setProperty("variant", "inner")
        results_tabs.setDocumentMode(True)

        self.process_results = QTextEdit()
        self.process_results.setReadOnly(True)
        self.process_results.setProperty("readOnlyValue", "true")
        self.process_results.setPlaceholderText(
            "A summary of the first and last state appears here once the "
            "process has been simulated.")
        results_tabs.addTab(self.process_results, "Summary")

        self.process_table = ly.results_table(
            [], empty_text="Every state along the path is tabulated here "
                           "after a simulation.",
            stretch_last=False,
        )
        results_tabs.addTab(self.process_table, "Data table")

        self.process_plot_canvas = PlotCanvas(
            self, width=10, height=6,
            empty_text="The path is plotted here after a simulation.")
        results_tabs.addTab(self.process_plot_canvas, "Process plot")

        return results_tabs

    # -- Dynamic label helpers --------------------------------------------

    def _update_final_label(self, process_text: str):
        label_text, unit, is_pressure = _PROCESS_FINAL_META.get(
            process_text, ("Final value", "-", None)
        )
        self.final_label.setText(f"{label_text} ({unit})")

        # Adjust spinbox range and default value sensibly
        if is_pressure:
            self.final_condition.setRange(0.001, 10000)
            if self.final_condition.value() <= 0:
                self.final_condition.setValue(10.0)
        elif is_pressure is False:   # temperature
            self.final_condition.setRange(-273.14, 2000)
            if self.final_condition.value() <= 0.001:
                self.final_condition.setValue(100.0)

        # Show/hide polytropic n
        show_poly = (process_text == 'Polytropic')
        self.poly_n_label.setVisible(show_poly)
        self.poly_n.setVisible(show_poly)

    # -- Simulation --------------------------------------------------------

    def simulate_process(self):
        """Start background simulation"""
        if self._worker is not None and self._worker.isRunning():
            return

        fluid = self.proc_fluid_combo.currentText()
        initial_T = self.init_temp.value() + 273.15      # K
        initial_P = self.init_pres.value() * 1e5         # Pa
        process_type = self.process_type.currentText()
        final_value = self.final_condition.value()
        num_points = self.num_points.value()
        polytropic_n = self.poly_n.value()

        # Convert final_value to SI
        _, _, is_pressure = _PROCESS_FINAL_META.get(process_type,
                                                    (None, None, None))
        if is_pressure:
            final_value_si = final_value * 1e5          # bar -> Pa
        else:
            final_value_si = final_value + 273.15       # °C -> K

        ly.set_status(self.status, "")

        # The whole input group feeds this computation, so all of it is
        # disabled while the simulation runs.
        self._busy = BusyGuard(
            self,
            [self.proc_calc_btn, self.proc_fluid_combo, self.process_type,
             self.init_temp, self.init_pres, self.final_condition,
             self.num_points, self.poly_n],
            f"Simulating the {process_type.lower()} path for {fluid}...")
        self._busy.start()

        self._worker = Worker(
            self.calc.simulate_process_path,
            fluid=fluid,
            process_type=process_type,
            initial_T=initial_T,
            initial_P=initial_P,
            final_value=final_value_si,
            num_points=num_points,
            polytropic_n=polytropic_n,
        )
        self._worker.done.connect(
            lambda r: self._on_simulation_done(r, fluid, process_type,
                                               final_value))
        self._worker.failed.connect(self._on_simulation_error)
        self._worker.start()

    def _on_simulation_done(self, results: dict, fluid: str,
                            process_type: str, final_value: float):
        self._busy.stop(
            f"{len(results['Temperature'])} states simulated for {fluid}")

        _, unit, _ = _PROCESS_FINAL_META.get(process_type,
                                             ("Final value", "-", None))

        # -- Summary (values converted to display units) ------------------
        summary = (
            f"Process path simulation\n"
            f"Fluid: {fluid}\n"
            f"Process: {process_type}\n"
            f"Initial T: {self.init_temp.value():.2f} °C\n"
            f"Initial P: {self.init_pres.value():.4g} bar\n"
            f"Final value: {final_value:.4g} {unit}\n"
        )
        if process_type == 'Polytropic':
            summary += f"Polytropic n: {self.poly_n.value():.3f}\n"
        summary += f"Points: {len(results['Temperature'])}\n\n"

        for state_label, idx in (("First state:", 0), ("Last state:", -1)):
            summary += f"{state_label}\n"
            for key, arr in results.items():
                if isinstance(arr, np.ndarray) and arr.size:
                    header, conv = _DISPLAY_COLUMNS.get(key, (key, None))
                    val = arr[idx]
                    if conv is not None and isinstance(val, (int, float,
                                                             np.floating)):
                        val = conv(float(val))
                    summary += f"  {header}: {self._fmt(val)}\n"
            summary += "\n"
        self.process_results.setPlainText(summary)

        # -- Data table (display units in headers) ------------------------
        props = list(results.keys())
        headers = [_DISPLAY_COLUMNS.get(key, (key, None))[0] for key in props]
        self.process_table.setColumnCount(len(props))
        self.process_table.setHorizontalHeaderLabels(headers)

        rows = []
        for i in range(len(results[props[0]])):
            row = []
            for key in props:
                val = results[key][i]
                _, conv = _DISPLAY_COLUMNS.get(key, (key, None))
                if conv is not None and isinstance(val, (int, float,
                                                         np.floating)):
                    val = conv(float(val))
                row.append(self._fmt(val))
            rows.append(row)
        numeric = tuple(i for i, key in enumerate(props) if key != 'Phase')
        ly.fill_table(self.process_table, rows, numeric_columns=numeric)

        # -- Plot (canvas expects SI arrays) ------------------------------
        self.process_plot_canvas.plot_process_path(results, process_type, fluid)

    def _on_simulation_error(self, msg: str):
        self._busy.stop("Simulation failed")
        ly.set_status(self.status,
                      f"Could not simulate this process: {msg}", "error")

    @staticmethod
    def _fmt(val) -> str:
        """Format a single value for display."""
        if isinstance(val, (float, np.floating)):
            if np.isnan(val):
                return "N/A"
            if abs(val) >= 1e8 or (val != 0 and abs(val) < 1e-8):
                return f"{val:.4e}"
            return f"{val:.6g}"
        return str(val)

    # -- Integration with main window (export / project / clear) ----------

    def get_results(self):
        """Return the current data table as a DataFrame, or None if empty."""
        nrow = self.process_table.rowCount()
        ncol = self.process_table.columnCount()
        if nrow == 0 or ncol == 0:
            return None
        headers = []
        for col in range(ncol):
            item = self.process_table.horizontalHeaderItem(col)
            headers.append(item.text() if item else f"Column_{col}")
        return pd.DataFrame(ly.table_rows(self.process_table), columns=headers)

    def clear_data(self):
        """Clear results, table and plot."""
        self.process_results.clear()
        self.process_table.setRowCount(0)
        self.process_table.setColumnCount(0)
        self.process_plot_canvas.clear()
        ly.set_status(self.status, "")

    def get_tab_data(self):
        """Serializable snapshot of the tab's inputs."""
        return {
            'fluid': self.proc_fluid_combo.currentText(),
            'initial_T_C': self.init_temp.value(),
            'initial_P_bar': self.init_pres.value(),
            'process': self.process_type.currentText(),
            'final_value': self.final_condition.value(),
            'polytropic_n': self.poly_n.value(),
            'num_points': self.num_points.value(),
        }

    def load_tab_data(self, data):
        """Restore the tab's inputs from a snapshot."""
        if 'fluid' in data:
            self.proc_fluid_combo.setCurrentText(data['fluid'])
        if 'process' in data:
            self.process_type.setCurrentText(data['process'])
        if 'initial_T_C' in data:
            self.init_temp.setValue(data['initial_T_C'])
        if 'initial_P_bar' in data:
            self.init_pres.setValue(data['initial_P_bar'])
        if 'final_value' in data:
            self.final_condition.setValue(data['final_value'])
        if 'polytropic_n' in data:
            self.poly_n.setValue(data['polytropic_n'])
        if 'num_points' in data:
            self.num_points.setValue(data['num_points'])
