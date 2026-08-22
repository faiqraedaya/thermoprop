import numpy as np
import pandas as pd
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QGroupBox,
                             QComboBox, QLabel, QDoubleSpinBox, QPushButton,
                             QTableWidget, QTabWidget, QTextEdit, QSpinBox,
                             QMessageBox, QTableWidgetItem)
from PySide6.QtCore import QThread, Signal

from ..core.plot_canvas import PlotCanvas


# ---------------------------------------------------------------------------
# Background worker – runs simulate_process_path off the GUI thread
# ---------------------------------------------------------------------------

class _SimulationWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, calc, fluid, process_type, initial_T, initial_P,
                 final_value, num_points, polytropic_n):
        super().__init__()
        self.calc = calc
        self.fluid = fluid
        self.process_type = process_type
        self.initial_T = initial_T
        self.initial_P = initial_P
        self.final_value = final_value
        self.num_points = num_points
        self.polytropic_n = polytropic_n

    def run(self):
        try:
            results = self.calc.simulate_process_path(
                fluid=self.fluid,
                process_type=self.process_type,
                initial_T=self.initial_T,
                initial_P=self.initial_P,
                final_value=self.final_value,
                num_points=self.num_points,
                polytropic_n=self.polytropic_n,
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Tab widget
# ---------------------------------------------------------------------------

# Maps process type → (final_value label text, unit string, is_pressure)
_PROCESS_FINAL_META = {
    'Isobaric':    ("Final Temperature", "°C",  False),
    'Isochoric':   ("Final Temperature", "°C",  False),
    'Isothermal':  ("Final Pressure",    "bar", True),
    'Isenthalpic': ("Final Pressure",    "bar", True),
    'Isentropic':  ("Final Pressure",    "bar", True),
    'Polytropic':  ("Final Pressure",    "bar", True),
}

# Maps SI result keys → (display header with unit, conversion from SI)
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
        """Create process path simulation tab"""
        layout = QVBoxLayout(self)

        # ── Input section ────────────────────────────────────────────────
        input_group = QGroupBox("Process Path Definition")
        input_layout = QGridLayout(input_group)

        # Fluid
        input_layout.addWidget(QLabel("Fluid:"), 0, 0)
        self.proc_fluid_combo = QComboBox()
        self.proc_fluid_combo.addItems(self.calc.fluids)
        self.proc_fluid_combo.setCurrentText('Water')
        input_layout.addWidget(self.proc_fluid_combo, 0, 1)

        # Initial state
        input_layout.addWidget(QLabel("Initial T (°C):"), 1, 0)
        self.init_temp = QDoubleSpinBox()
        self.init_temp.setRange(-273.14, 2000)
        self.init_temp.setValue(25)
        input_layout.addWidget(self.init_temp, 1, 1)

        input_layout.addWidget(QLabel("Initial P (bar):"), 1, 2)
        self.init_pres = QDoubleSpinBox()
        self.init_pres.setRange(0.001, 10000)
        self.init_pres.setValue(1.01325)
        input_layout.addWidget(self.init_pres, 1, 3)

        # Process type
        input_layout.addWidget(QLabel("Process:"), 2, 0)
        self.process_type = QComboBox()
        self.process_type.addItems(list(_PROCESS_FINAL_META.keys()))
        self.process_type.currentTextChanged.connect(self._update_final_label)
        input_layout.addWidget(self.process_type, 2, 1)

        # Final condition – label updates dynamically
        self.final_label = QLabel("Final Temperature (°C):")
        input_layout.addWidget(self.final_label, 2, 2)
        self.final_condition = QDoubleSpinBox()
        self.final_condition.setRange(-273.14, 10000)
        self.final_condition.setValue(100)
        input_layout.addWidget(self.final_condition, 2, 3)

        # Polytropic exponent (shown only for Polytropic)
        self.poly_n_label = QLabel("Polytropic n:")
        input_layout.addWidget(self.poly_n_label, 3, 0)
        self.poly_n = QDoubleSpinBox()
        self.poly_n.setRange(0.01, 10.0)
        self.poly_n.setSingleStep(0.05)
        self.poly_n.setValue(1.3)
        self.poly_n.setDecimals(3)
        input_layout.addWidget(self.poly_n, 3, 1)

        # Number of points
        input_layout.addWidget(QLabel("Points:"), 3, 2)
        self.num_points = QSpinBox()
        self.num_points.setRange(10, 1000)
        self.num_points.setValue(50)
        input_layout.addWidget(self.num_points, 3, 3)

        layout.addWidget(input_group)

        # Initialise dynamic label + poly_n visibility
        self._update_final_label(self.process_type.currentText())

        # ── Calculate button ─────────────────────────────────────────────
        self.proc_calc_btn = QPushButton("Simulate Process")
        self.proc_calc_btn.clicked.connect(self.simulate_process)
        layout.addWidget(self.proc_calc_btn)

        # ── Results in tabs ───────────────────────────────────────────────
        results_tabs = QTabWidget()

        self.process_results = QTextEdit()
        results_tabs.addTab(self.process_results, "Summary")

        self.process_table = QTableWidget()
        results_tabs.addTab(self.process_table, "Data Table")

        self.process_plot_canvas = PlotCanvas(self, width=10, height=6)
        results_tabs.addTab(self.process_plot_canvas, "Process Plot")

        layout.addWidget(results_tabs)
        self.setLayout(layout)

    # ── Dynamic label helpers ────────────────────────────────────────────

    def _update_final_label(self, process_text: str):
        label_text, unit, is_pressure = _PROCESS_FINAL_META.get(
            process_text, ("Final Value", "—", None)
        )
        self.final_label.setText(f"{label_text} ({unit}):")

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

    # ── Simulation ────────────────────────────────────────────────────────

    def simulate_process(self):
        """Start background simulation"""
        if self._worker and self._worker.isRunning():
            return  # already running

        fluid = self.proc_fluid_combo.currentText()
        initial_T = self.init_temp.value() + 273.15      # K
        initial_P = self.init_pres.value() * 1e5          # Pa
        process_type = self.process_type.currentText()
        final_value = self.final_condition.value()
        num_points = self.num_points.value()
        polytropic_n = self.poly_n.value()

        # Convert final_value to SI
        _, _, is_pressure = _PROCESS_FINAL_META.get(process_type, (None, None, None))
        if is_pressure:
            final_value_si = final_value * 1e5          # bar → Pa
        else:
            final_value_si = final_value + 273.15       # °C → K

        # Disable button and update status during background calc
        self.proc_calc_btn.setEnabled(False)
        self.proc_calc_btn.setText("Simulating…")

        self._worker = _SimulationWorker(
            self.calc, fluid, process_type, initial_T, initial_P,
            final_value_si, num_points, polytropic_n
        )
        self._worker.finished.connect(lambda r: self._on_simulation_done(r, fluid, process_type, final_value))
        self._worker.error.connect(self._on_simulation_error)
        self._worker.start()

    def _on_simulation_done(self, results: dict, fluid: str, process_type: str, final_value: float):
        self.proc_calc_btn.setEnabled(True)
        self.proc_calc_btn.setText("Simulate Process")

        _, unit, is_pressure = _PROCESS_FINAL_META.get(process_type, ("Final Value", "—", None))

        # ── Summary (values converted to display units) ──────────────────
        summary = (
            f"Process Path Simulation\n"
            f"Fluid: {fluid}\n"
            f"Process: {process_type}\n"
            f"Initial T: {self.init_temp.value():.2f} °C\n"
            f"Initial P: {self.init_pres.value():.4g} bar\n"
            f"Final Value: {final_value:.4g} {unit}\n"
        )
        if process_type == 'Polytropic':
            summary += f"Polytropic n: {self.poly_n.value():.3f}\n"
        summary += f"Points: {len(results['Temperature'])}\n\n"

        for state_label, idx in (("First State:", 0), ("Last State:", -1)):
            summary += f"{state_label}\n"
            for key, arr in results.items():
                if isinstance(arr, np.ndarray) and arr.size:
                    header, conv = _DISPLAY_COLUMNS.get(key, (key, None))
                    val = arr[idx]
                    if conv is not None and isinstance(val, (int, float, np.floating)):
                        val = conv(float(val))
                    summary += f"  {header}: {self._fmt(val)}\n"
            summary += "\n"
        self.process_results.setPlainText(summary)

        # ── Data table (display units in headers) ────────────────────────
        props = list(results.keys())
        headers = [_DISPLAY_COLUMNS.get(key, (key, None))[0] for key in props]
        nrow = len(results[props[0]])
        self.process_table.setRowCount(nrow)
        self.process_table.setColumnCount(len(props))
        self.process_table.setHorizontalHeaderLabels(headers)
        for i in range(nrow):
            for j, key in enumerate(props):
                val = results[key][i]
                _, conv = _DISPLAY_COLUMNS.get(key, (key, None))
                if conv is not None and isinstance(val, (int, float, np.floating)):
                    val = conv(float(val))
                self.process_table.setItem(i, j, QTableWidgetItem(self._fmt(val)))
        self.process_table.resizeColumnsToContents()

        # ── Plot (canvas expects SI arrays) ──────────────────────────────
        self.process_plot_canvas.plot_process_path(results, process_type, fluid)

    def _on_simulation_error(self, msg: str):
        self.proc_calc_btn.setEnabled(True)
        self.proc_calc_btn.setText("Simulate Process")
        QMessageBox.critical(self, "Simulation Error", f"Failed to simulate process: {msg}")

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

    # ── Integration with main window (export / project / clear) ─────────

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
        rows = []
        for row in range(nrow):
            rows.append([
                self.process_table.item(row, col).text()
                if self.process_table.item(row, col) else ""
                for col in range(ncol)
            ])
        return pd.DataFrame(rows, columns=headers)

    def clear_data(self):
        """Clear results, table and plot."""
        self.process_results.clear()
        self.process_table.setRowCount(0)
        self.process_table.setColumnCount(0)
        self.process_plot_canvas.clear()

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
