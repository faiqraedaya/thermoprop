from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QMessageBox, QGroupBox,
    QDialog, QDialogButtonBox,
)

from ..core.mixture_component import MixtureComponent

class MixtureDialog(QDialog):
    """Dialog for defining mixture compositions"""

    def __init__(self, parent=None, predefined_mixtures=None, fluids=None):
        super().__init__(parent)
        self.predefined_mixtures = predefined_mixtures or {}
        self.fluids = fluids
        self.components = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Mixture Designer')
        self.setGeometry(200, 200, 600, 500)

        layout = QVBoxLayout(self)

        # Predefined mixtures
        pred_group = QGroupBox("Predefined Mixtures")
        pred_layout = QHBoxLayout(pred_group)

        self.pred_combo = QComboBox()
        self.pred_combo.addItem("Custom Mixture")
        self.pred_combo.addItems(list(self.predefined_mixtures.keys()))
        pred_layout.addWidget(QLabel("Select:"))
        pred_layout.addWidget(self.pred_combo)

        load_pred_btn = QPushButton("Load")
        load_pred_btn.clicked.connect(self.load_predefined)
        pred_layout.addWidget(load_pred_btn)

        layout.addWidget(pred_group)

        # Component table
        comp_group = QGroupBox("Mixture Components")
        comp_layout = QVBoxLayout(comp_group)

        # Add component controls
        add_layout = QHBoxLayout()
        self.comp_combo = QComboBox()
        if self.fluids is None:
            from ..core.mixture_calculator import MixtureCalculator
            self.fluids = MixtureCalculator().fluids
        self.comp_combo.addItems(self.fluids)
        add_layout.addWidget(QLabel("Component:"))
        add_layout.addWidget(self.comp_combo)

        add_btn = QPushButton("Add Component")
        add_btn.clicked.connect(self.add_component)
        add_layout.addWidget(add_btn)

        comp_layout.addLayout(add_layout)

        # Components table
        self.comp_table = QTableWidget()
        self.comp_table.setColumnCount(4)
        self.comp_table.setHorizontalHeaderLabels([
            'Component', 'Mole Fraction', 'Mass Fraction', 'Actions'
        ])
        self.comp_table.horizontalHeader().setStretchLastSection(True)
        comp_layout.addWidget(self.comp_table)

        # Connect editing signals for the table
        self.comp_table.itemChanged.connect(self.update_from_table)

        # Normalization controls
        norm_layout = QHBoxLayout()
        norm_mole_btn = QPushButton("Normalize Mole Fractions")
        norm_mole_btn.clicked.connect(self.normalize_mole_fractions)
        norm_layout.addWidget(norm_mole_btn)

        norm_mass_btn = QPushButton("Normalize Mass Fractions")
        norm_mass_btn.clicked.connect(self.normalize_mass_fractions)
        norm_layout.addWidget(norm_mass_btn)

        comp_layout.addLayout(norm_layout)

        layout.addWidget(comp_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

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
                QMessageBox.critical(self, "Invalid Component", str(e))
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
                QMessageBox.warning(self, "Warning", "Component already exists!")
                return

        try:
            comp = MixtureComponent(comp_name, 0.0)
        except ValueError as e:
            QMessageBox.critical(self, "Invalid Component", str(e))
            return
        self.components.append(comp)
        self.comp_table.blockSignals(True)
        self.add_component_to_table(comp)
        self.comp_table.blockSignals(False)

    def add_component_to_table(self, component):
        """Add component to table widget"""
        row = self.comp_table.rowCount()
        self.comp_table.insertRow(row)

        # Component name
        self.comp_table.setItem(row, 0, QTableWidgetItem(component.name))

        # Mole fraction
        mole_item = QTableWidgetItem(f"{component.mole_fraction:.4f}")
        self.comp_table.setItem(row, 1, mole_item)

        # Mass fraction
        mass_item = QTableWidgetItem(f"{component.mass_fraction:.4f}")
        self.comp_table.setItem(row, 2, mass_item)

        # Remove button — the row is resolved at click time (rows shift after
        # removals, so a captured index would delete the wrong component)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_clicked)
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
            self.components.pop(row)
            self.comp_table.removeRow(row)
            self.update_table()

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
            if mass_item is not None:
                try:
                    comp.mass_fraction = float(mass_item.text())
                except ValueError:
                    self._revert_item(mass_item, comp.mass_fraction)

    def _revert_item(self, item, value):
        """Restore a table cell to the stored value (visible feedback for bad input)."""
        self.comp_table.blockSignals(True)
        item.setText(f"{value:.4f}")
        self.comp_table.blockSignals(False)

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
            comp.mass_fraction = (comp.mole_fraction * comp.molecular_weight) / (avg_mw * total_moles)

    def calculate_mole_fractions(self):
        """Calculate mole fractions from mass fractions"""
        total_mass = sum(comp.mass_fraction for comp in self.components)
        if total_mass == 0:
            return

        # Calculate mole fractions
        total_moles = sum(comp.mass_fraction / comp.molecular_weight
                         for comp in self.components)

        for comp in self.components:
            comp.mole_fraction = (comp.mass_fraction / comp.molecular_weight) / total_moles

    def update_table(self):
        """Update table display"""
        self.comp_table.blockSignals(True)
        for row, comp in enumerate(self.components):
            mole_item = self.comp_table.item(row, 1)
            mass_item = self.comp_table.item(row, 2)
            if mole_item is not None:
                mole_item.setText(f"{comp.mole_fraction:.4f}")
            if mass_item is not None:
                mass_item.setText(f"{comp.mass_fraction:.4f}")
        self.comp_table.blockSignals(False)

    def get_mixture(self):
        """Get final mixture as a list of (name, mole_fraction) tuples"""
        self.update_from_table()
        return [(comp.name, comp.mole_fraction) for comp in self.components]
