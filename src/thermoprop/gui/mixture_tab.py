import math

import pandas as pd
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QInputDialog, QWidget,
)

from . import layout as ly
from .worker import BusyGuard, Worker

_MIXTURE_COLUMNS = ['Property', 'Value', 'Unit']

_COMPONENT_COLUMNS = [
    'Component', 'Mole fraction', 'Mass fraction', 'Molar mass (g/mol)',
    'Partial pressure (bar)', 'Phase', 'Density (kg/m³)', 'Cp (kJ/kg·K)',
    'Viscosity (µPa·s)', 'Conductivity (W/m·K)',
]


class MixtureTab(QWidget):
    def __init__(self, calc, parent=None):
        super().__init__(parent)
        self.calc = calc
        self._main_window = parent
        self.current_components = []  # Stores List[MixtureComponent]
        self._worker = None
        self.init_ui()

    def init_ui(self):
        """Mixture tab: composition and state on the left, results on the right."""
        layout = ly.hbox(self, spacing=0)

        layout.addWidget(ly.splitter(
            self._build_input_panel(),
            self._build_results_panel(),
            sizes=[460, 940], stretch=[0, 1]))

    # -- Input panel ------------------------------------------------------

    def _build_input_panel(self) -> QWidget:
        panel, panel_layout = ly.panel()
        panel.setMinimumWidth(380)

        comp_section = ly.vbox()
        comp_section.addWidget(ly.heading("Composition"))

        model_form = ly.form()
        self.mixture_model = ly.choice_field(QComboBox())
        self.mixture_model.addItems(self.calc.mixture_models)
        self.mixture_model.setToolTip(
            "Ideal Gas mixes each component at its partial pressure. "
            "Humid Air uses the moist-air property basis.")
        model_form.addRow(ly.field_label("Mixing model"), self.mixture_model)
        comp_section.addLayout(model_form)

        btn_row = ly.hbox()
        btn_row.addWidget(ly.button("Define mixture...",
                                    on_click=self.define_mixture))
        btn_row.addWidget(ly.button("Load predefined...",
                                    on_click=self.load_predefined_mixture))
        btn_row.addStretch()
        comp_section.addLayout(btn_row)

        # The composition itself is a result, not something typed here, so it
        # gets a table rather than a free-text box.
        self.mixture_display = ly.results_table(
            ['Component', 'Mole fraction'],
            empty_text="No mixture defined yet.\n"
                       "Choose Define mixture or Load predefined.",
        )
        self.mixture_display.setMinimumHeight(140)
        self.mixture_display.setMaximumHeight(220)
        comp_section.addWidget(self.mixture_display)

        self.composition_status = ly.status_label()
        comp_section.addWidget(self.composition_status)
        panel_layout.addLayout(comp_section)

        state_section = ly.vbox()
        state_section.addWidget(ly.heading("State"))

        state_grid = ly.grid()
        state_grid.addWidget(ly.field_label("Temperature"), 0, 0)
        self.mix_temp = QDoubleSpinBox()
        self.mix_temp.setRange(-273.14, 2000)
        self.mix_temp.setDecimals(3)
        self.mix_temp.setValue(25)
        ly.value_field(self.mix_temp)
        state_grid.addWidget(self.mix_temp, 0, 1)
        state_grid.addWidget(ly.unit_label("°C"), 0, 2)

        state_grid.addWidget(ly.field_label("Pressure"), 1, 0)
        self.mix_pres = QDoubleSpinBox()
        self.mix_pres.setRange(0.001, 1000)
        self.mix_pres.setDecimals(5)
        self.mix_pres.setValue(1.01325)
        ly.value_field(self.mix_pres)
        state_grid.addWidget(self.mix_pres, 1, 1)
        state_grid.addWidget(ly.unit_label("bar"), 1, 2)

        state_grid.setColumnStretch(1, 1)
        state_grid.setColumnStretch(2, 0)
        state_section.addLayout(state_grid)
        panel_layout.addLayout(state_section)

        self.calc_btn = ly.button("Calculate mixture properties",
                                  variant="primary",
                                  on_click=self.calculate_mixture)
        panel_layout.addLayout(ly.action_row(self.calc_btn))

        self.calc_status = ly.status_label()
        panel_layout.addWidget(self.calc_status)

        panel_layout.addStretch()
        return panel

    # -- Results panel ----------------------------------------------------

    def _build_results_panel(self) -> QWidget:
        panel, panel_layout = ly.panel()
        panel.setMinimumWidth(420)

        mix_section = ly.vbox()
        mix_section.addWidget(ly.heading("Mixture properties"))
        self.mixture_results_table = ly.results_table(
            _MIXTURE_COLUMNS,
            empty_text="Mixture properties appear here after a calculation.",
        )
        mix_section.addWidget(self.mixture_results_table)
        panel_layout.addLayout(mix_section, 1)

        comp_section = ly.vbox()
        comp_section.addWidget(ly.heading("Components at these conditions"))
        comp_section.addWidget(ly.caption(
            "Each component evaluated at its own partial pressure - the same "
            "basis the mixing rules use."))
        self.component_table = ly.results_table(
            _COMPONENT_COLUMNS,
            empty_text="Per-component values appear here alongside the "
                       "mixture result.",
            stretch_last=False,
        )
        comp_section.addWidget(self.component_table)
        panel_layout.addLayout(comp_section, 1)
        return panel

    # -- Composition ------------------------------------------------------

    def define_mixture(self):
        """Define mixture composition"""
        if self._main_window and hasattr(self._main_window, 'open_mixture_designer'):
            self._main_window.open_mixture_designer()
        else:
            ly.set_status(self.composition_status,
                          "Could not open the mixture designer.", "error")

    def load_predefined_mixture(self):
        """Load predefined mixture"""
        mixture_name, ok = QInputDialog.getItem(
            self, "Load predefined mixture",
            "Select mixture:",
            list(self.calc.predefined_mixtures.keys()),
            0, False
        )

        if ok and mixture_name:
            tuples = self.calc.predefined_mixtures[mixture_name]
            if self._store_and_display(tuples):
                ly.set_status(self.composition_status,
                              f"Loaded the {mixture_name} mixture.", "success")

    def _store_and_display(self, components) -> bool:
        """Convert (name, mole_fraction) tuples to MixtureComponent list and display.

        Returns True on success; shows an error and keeps the previous mixture
        if any component name is invalid.
        """
        from ..core.mixture_component import MixtureComponent
        try:
            new_components = [MixtureComponent(name, frac)
                              for name, frac in components]
        except ValueError as e:
            ly.set_status(self.composition_status, str(e), "error")
            return False

        self.current_components = new_components
        ly.fill_table(
            self.mixture_display,
            [[c.name, f"{c.mole_fraction:.4f}"] for c in self.current_components],
            numeric_columns=(1,),
        )

        total = sum(c.mole_fraction for c in self.current_components)
        if abs(total - 1.0) > 1e-4:
            ly.set_status(
                self.composition_status,
                f"Mole fractions sum to {total:.4f}, not 1.0. "
                f"Normalise them in the mixture designer.", "warning")
        else:
            ly.set_status(self.composition_status, "")
        return True

    def display_mixture(self, components):
        """Display mixture composition (legacy: accepts (name, fraction) tuples)."""
        self._store_and_display(components)

    def update_mixture_display(self, components):
        """Update mixture display from main window."""
        self._store_and_display(components)

    # -- Calculation ------------------------------------------------------

    def calculate_mixture(self):
        """Calculate mixture properties"""
        if self._worker is not None and self._worker.isRunning():
            return

        if not self.current_components:
            ly.set_status(self.calc_status,
                          "Define a mixture before calculating.", "error")
            return

        total = sum(c.mole_fraction for c in self.current_components)
        if total <= 0:
            ly.set_status(self.calc_status,
                          "Mole fractions sum to zero, so there is nothing "
                          "to evaluate.", "error")
            return

        ly.set_status(self.calc_status, "")

        T = self.mix_temp.value() + 273.15   # K
        P = self.mix_pres.value() * 1e5      # Pa
        model = self.mixture_model.currentText()
        components = list(self.current_components)

        def work():
            results, error = self.calc.calculate_mixture_properties(
                components, T, P, model)
            if error:
                raise ValueError(error)
            return results, self.calc.component_properties(components, T, P)

        self._busy = BusyGuard(
            self, [self.calc_btn, self.mix_temp, self.mix_pres,
                   self.mixture_model],
            f"Calculating {model} mixture properties...")
        self._busy.start()

        self._worker = Worker(work)
        self._worker.done.connect(self._on_results)
        self._worker.failed.connect(self._on_failure)
        self._worker.start()

    def _on_results(self, payload):
        results, component_rows = payload
        self._busy.stop(f"{len(results)} mixture properties calculated")
        self.display_mixture_results(results)
        self.display_component_results(component_rows)

    def _on_failure(self, message):
        self._busy.stop("Mixture calculation failed")
        ly.set_status(self.calc_status, message, "error")

    def display_mixture_results(self, results):
        """Display mixture calculation results"""
        rows = [[name, self._format(value), unit]
                for name, (value, unit) in results.items()]
        ly.fill_table(self.mixture_results_table, rows, numeric_columns=(1,))

    def display_component_results(self, component_rows):
        """Fill the per-component comparison table."""
        rows = []
        for row in component_rows:
            rows.append([
                row['name'],
                self._format(row['mole_fraction']),
                self._format(row['mass_fraction']),
                self._format(row['molar_mass']),
                self._format(row['partial_pressure'] / 1e5),
                str(row['phase']),
                self._format(row['density']),
                self._format(row['cp'] / 1000),
                self._format(row['viscosity'] * 1e6),
                self._format(row['conductivity']),
            ])
        ly.fill_table(self.component_table, rows,
                      numeric_columns=(1, 2, 3, 4, 6, 7, 8, 9))

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
        """Return current mixture results as a DataFrame, or None if empty."""
        rows = ly.table_rows(self.mixture_results_table)
        if not rows:
            return None
        return pd.DataFrame(rows, columns=_MIXTURE_COLUMNS)

    def clear_data(self):
        """Clear mixture definition and results."""
        self.current_components = []
        self.mixture_display.setRowCount(0)
        self.mixture_results_table.setRowCount(0)
        self.component_table.setRowCount(0)
        ly.set_status(self.composition_status, "")
        ly.set_status(self.calc_status, "")

    def get_tab_data(self):
        """Serializable snapshot of the tab's inputs."""
        return {
            'model': self.mixture_model.currentText(),
            'temperature_C': self.mix_temp.value(),
            'pressure_bar': self.mix_pres.value(),
            'components': [(c.name, c.mole_fraction)
                           for c in self.current_components],
        }

    def load_tab_data(self, data):
        """Restore the tab's inputs from a snapshot."""
        if 'model' in data:
            self.mixture_model.setCurrentText(data['model'])
        if 'temperature_C' in data:
            self.mix_temp.setValue(data['temperature_C'])
        if 'pressure_bar' in data:
            self.mix_pres.setValue(data['pressure_bar'])
        if data.get('components'):
            self._store_and_display(data['components'])
