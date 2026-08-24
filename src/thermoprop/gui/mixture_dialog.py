from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHeaderView,
)

from ..core.mixture_component import MixtureComponent
from . import layout as ly
from .theme import Tokens, restyle

_COLUMNS = ['Component', 'Mole fraction', 'Mass fraction', '']


class MixtureDialog(QDialog):
    """Dialog for defining mixture compositions"""

    # Wide enough for the row's Remove button plus its cell padding
    ACTION_COLUMN_W = 104

    def __init__(self, parent=None, predefined_mixtures=None, fluids=None):
        super().__init__(parent)
        self.predefined_mixtures = predefined_mixtures or {}
        self.fluids = fluids
        self.components = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Mixture designer')
        self.setMinimumWidth(640)
        self.setMinimumHeight(560)

        layout = ly.window_layout(self)

        # Start from a predefined mixture, or build one component by component
        start_section = ly.vbox()
        start_section.addWidget(ly.heading("Start from"))

        pred_row = ly.hbox()
        pred_row.addWidget(ly.field_label("Predefined mixture"))
        self.pred_combo = ly.choice_field(QComboBox(), min_width=200)
        self.pred_combo.addItem("Custom mixture")
        self.pred_combo.addItems(list(self.predefined_mixtures.keys()))
        pred_row.addWidget(self.pred_combo, 1)
        pred_row.addWidget(ly.button("Load", on_click=self.load_predefined))
        start_section.addLayout(pred_row)
        layout.addLayout(start_section)

        # Components
        comp_section = ly.vbox()
        comp_section.addWidget(ly.heading("Components"))
        comp_section.addWidget(ly.caption(
            "Double-click a fraction to edit it. Mole and mass fractions are "
            "kept consistent when you normalise."))

        add_row = ly.hbox()
        add_row.addWidget(ly.field_label("Component"))
        self.comp_combo = ly.choice_field(QComboBox(), min_width=200)
        if self.fluids is None:
            from ..core.mixture_calculator import MixtureCalculator
            self.fluids = MixtureCalculator().fluids
        self.comp_combo.addItems(self.fluids)
        add_row.addWidget(self.comp_combo, 1)
        add_row.addWidget(ly.button("Add component", on_click=self.add_component))
        comp_section.addLayout(add_row)

        self.comp_table = ly.results_table(
            _COLUMNS,
            empty_text="No components yet.\n"
                       "Add one above, or load a predefined mixture.",
            stretch_last=False,
            editable=True,
        )
        # The name takes the slack; the fractions size to their content; the
        # action column is fixed wide enough that its button never clips
        # (resizeColumnsToContents does not measure cell widgets).
        header = self.comp_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QHeaderView.Stretch)
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.comp_table.setColumnWidth(3, self.ACTION_COLUMN_W)
        comp_section.addWidget(self.comp_table, 1)

        # Connect editing signals for the table
        self.comp_table.itemChanged.connect(self.update_from_table)

        norm_row = ly.hbox()
        norm_row.addWidget(ly.button(
            "Normalise mole fractions", on_click=self.normalize_mole_fractions,
            tooltip="Scale every mole fraction so they sum to 1."))
        norm_row.addWidget(ly.button(
            "Normalise mass fractions", on_click=self.normalize_mass_fractions,
            tooltip="Scale every mass fraction so they sum to 1, then "
                    "recompute the mole fractions."))
        norm_row.addStretch()
        comp_section.addLayout(norm_row)

        self.status = ly.status_label()
        comp_section.addWidget(self.status)
        layout.addLayout(comp_section, 1)

        # Dialog buttons: the primary action sits on the trailing side, which
        # QDialogButtonBox arranges per platform.
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        ok_button = button_box.button(QDialogButtonBox.Ok)
        ok_button.setText("Use this mixture")
        ok_button.setProperty("variant", "primary")
        ok_button.setMinimumHeight(Tokens.CONTROL_HEIGHT)
        restyle(ok_button)
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        cancel_button.setMinimumHeight(Tokens.CONTROL_HEIGHT)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    # -- Composition editing ----------------------------------------------

    def load_predefined(self):
        """Load predefined mixture"""
        mixture_name = self.pred_combo.currentText()
        if mixture_name in self.predefined_mixtures:
            self.components.clear()
            self.comp_table.blockSignals(True)
            self.comp_table.setRowCount(0)

            try:
                for comp_name, mole_frac in self.predefined_mixtures[mixture_name]:
                    comp = MixtureComponent(comp_name, mole_frac)
                    self.components.append(comp)
                    self.add_component_to_table(comp)
            except ValueError as e:
                ly.set_status(self.status, str(e), "error")
            finally:
                self.comp_table.blockSignals(False)

            self.calculate_mass_fractions()
            self.update_table()

    def add_component(self):
        """Add new component to mixture"""
        comp_name = self.comp_combo.currentText()

        # Check if component already exists
        for comp in self.components:
            if comp.name == comp_name:
                ly.set_status(self.status,
                              f"{comp_name} is already in the mixture.",
                              "warning")
                return

        try:
            comp = MixtureComponent(comp_name, 0.0)
        except ValueError as e:
            ly.set_status(self.status, str(e), "error")
            return
        self.components.append(comp)
        self.comp_table.blockSignals(True)
        self.add_component_to_table(comp)
        self.comp_table.blockSignals(False)
        self._report_total()

    def add_component_to_table(self, component):
        """Add component to table widget"""
        row = self.comp_table.rowCount()
        self.comp_table.insertRow(row)

        name_item = ly.table_item(component.name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
        self.comp_table.setItem(row, 0, name_item)

        self.comp_table.setItem(
            row, 1, ly.table_item(f"{component.mole_fraction:.4f}", numeric=True))
        self.comp_table.setItem(
            row, 2, ly.table_item(f"{component.mass_fraction:.4f}", numeric=True))

        # Remove button - the row is resolved at click time (rows shift after
        # removals, so a captured index would delete the wrong component)
        remove_btn = ly.button("Remove", variant="quiet",
                               on_click=self._remove_clicked,
                               tooltip=f"Remove {component.name} from the mixture")
        self.comp_table.setCellWidget(row, 3, remove_btn)

    def _remove_clicked(self):
        """Remove the component whose row holds the clicked button."""
        btn = self.sender()
        for row in range(self.comp_table.rowCount()):
            if self.comp_table.cellWidget(row, 3) is btn:
                self.remove_component(row)
                return

    def remove_component(self, row):
        """Remove component from mixture"""
        if 0 <= row < len(self.components):
            name = self.components[row].name
            self.components.pop(row)
            self.comp_table.removeRow(row)
            self.update_table()
            ly.set_status(self.status, f"Removed {name}.", "success")

    def update_from_table(self):
        """Update components from table values; invalid entries are reverted."""
        for row in range(min(self.comp_table.rowCount(), len(self.components))):
            comp = self.components[row]
            mole_item = self.comp_table.item(row, 1)
            mass_item = self.comp_table.item(row, 2)
            if mole_item is not None:
                try:
                    comp.mole_fraction = float(mole_item.text())
                except ValueError:
                    self._revert_item(mole_item, comp.mole_fraction)
                    ly.set_status(
                        self.status,
                        f"'{mole_item.text()}' is not a number, so the mole "
                        f"fraction for {comp.name} was left unchanged.",
                        "error")
            if mass_item is not None:
                try:
                    comp.mass_fraction = float(mass_item.text())
                except ValueError:
                    self._revert_item(mass_item, comp.mass_fraction)
                    ly.set_status(
                        self.status,
                        f"'{mass_item.text()}' is not a number, so the mass "
                        f"fraction for {comp.name} was left unchanged.",
                        "error")
        self._report_total()

    def _revert_item(self, item, value):
        """Restore a table cell to the stored value (visible feedback for bad input)."""
        self.comp_table.blockSignals(True)
        item.setText(f"{value:.4f}")
        item.setToolTip(item.text())
        self.comp_table.blockSignals(False)

    def _report_total(self):
        """Say whether the mole fractions currently add up."""
        if not self.components:
            ly.set_status(self.status, "")
            return
        total = sum(comp.mole_fraction for comp in self.components)
        if abs(total - 1.0) > 1e-4:
            ly.set_status(
                self.status,
                f"Mole fractions sum to {total:.4f}, not 1.0. "
                f"Choose Normalise mole fractions to scale them.", "warning")
        else:
            ly.set_status(self.status,
                          "Mole fractions sum to 1.0.", "success")

    # -- Normalisation -----------------------------------------------------

    def normalize_mole_fractions(self):
        """Normalize mole fractions to sum to 1"""
        self.update_from_table()
        total = sum(comp.mole_fraction for comp in self.components)
        if total > 0:
            for comp in self.components:
                comp.mole_fraction /= total
        self.calculate_mass_fractions()
        self.update_table()

    def normalize_mass_fractions(self):
        """Normalize mass fractions to sum to 1"""
        self.update_from_table()
        total = sum(comp.mass_fraction for comp in self.components)
        if total > 0:
            for comp in self.components:
                comp.mass_fraction /= total
        self.calculate_mole_fractions()
        self.update_table()

    def calculate_mass_fractions(self):
        """Calculate mass fractions from mole fractions"""
        total_moles = sum(comp.mole_fraction for comp in self.components)
        if total_moles == 0:
            return

        # Calculate average molecular weight
        avg_mw = sum(comp.mole_fraction * comp.molecular_weight
                    for comp in self.components) / total_moles

        # Calculate mass fractions
        for comp in self.components:
            comp.mass_fraction = ((comp.mole_fraction * comp.molecular_weight)
                                  / (avg_mw * total_moles))

    def calculate_mole_fractions(self):
        """Calculate mole fractions from mass fractions"""
        total_mass = sum(comp.mass_fraction for comp in self.components)
        if total_mass == 0:
            return

        # Calculate mole fractions
        total_moles = sum(comp.mass_fraction / comp.molecular_weight
                         for comp in self.components)

        for comp in self.components:
            comp.mole_fraction = ((comp.mass_fraction / comp.molecular_weight)
                                  / total_moles)

    def update_table(self):
        """Update table display"""
        self.comp_table.blockSignals(True)
        for row, comp in enumerate(self.components):
            mole_item = self.comp_table.item(row, 1)
            mass_item = self.comp_table.item(row, 2)
            if mole_item is not None:
                mole_item.setText(f"{comp.mole_fraction:.4f}")
                mole_item.setToolTip(mole_item.text())
            if mass_item is not None:
                mass_item.setText(f"{comp.mass_fraction:.4f}")
                mass_item.setToolTip(mass_item.text())
        self.comp_table.blockSignals(False)
        self._report_total()

    def get_mixture(self):
        """Get final mixture as a list of (name, mole_fraction) tuples"""
        self.update_from_table()
        return [(comp.name, comp.mole_fraction) for comp in self.components]
