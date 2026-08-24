from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
)
import pint

from . import layout as ly

# Initialize unit registry
ureg = pint.UnitRegistry()

_UNIT_MAP = {
    'Temperature': ['°C', 'K', '°F', '°R'],
    'Pressure': ['Pa', 'kPa', 'MPa', 'bar', 'psi', 'atm', 'mmHg', 'inHg'],
    'Density': ['kg/m³', 'g/cm³', 'lb/ft³', 'kg/L'],
    'Energy': ['J', 'kJ', 'MJ', 'cal', 'kcal', 'BTU', 'kWh'],
    'Power': ['W', 'kW', 'MW', 'hp', 'BTU/h'],
    'Length': ['m', 'cm', 'mm', 'km', 'in', 'ft', 'yd', 'mile'],
    'Area': ['m²', 'cm²', 'mm²', 'km²', 'in²', 'ft²', 'acre'],
    'Volume': ['m³', 'L', 'mL', 'cm³', 'in³', 'ft³', 'gal', 'qt'],
    'Mass': ['kg', 'g', 'mg', 'lb', 'oz', 'tonne'],
    'Force': ['N', 'kN', 'lbf', 'kgf', 'dyne'],
}

_COMMON_CONVERSIONS = {
    'Temperature': [
        ('°C', '°F', '×9/5 + 32'),
        ('°C', 'K', '+ 273.15'),
        ('°F', '°C', '(×-32)×5/9'),
    ],
    'Pressure': [
        ('bar', 'psi', '× 14.504'),
        ('Pa', 'bar', '× 1e-5'),
        ('atm', 'Pa', '× 101325'),
    ],
    'Energy': [
        ('J', 'cal', '× 0.239'),
        ('kWh', 'J', '× 3.6e6'),
        ('BTU', 'J', '× 1055'),
    ],
}


class UnitConverterDialog(QDialog):
    """Unit conversion dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Unit converter')
        self.setMinimumWidth(520)
        self.setMinimumHeight(480)

        layout = ly.window_layout(self)

        # Property type
        type_section = ly.vbox()
        type_form = ly.form()
        self.prop_type = ly.choice_field(QComboBox())
        self.prop_type.addItems(list(_UNIT_MAP))
        self.prop_type.currentTextChanged.connect(self.update_units)
        type_form.addRow(ly.field_label("Property type"), self.prop_type)
        type_section.addLayout(type_form)
        layout.addLayout(type_section)

        # Conversion
        conv_section = ly.vbox()
        conv_section.addWidget(ly.heading("Convert"))

        conv_grid = ly.grid()
        conv_grid.addWidget(ly.field_label("From"), 0, 0)
        self.from_value = QDoubleSpinBox()
        self.from_value.setRange(-1e10, 1e10)
        self.from_value.setDecimals(6)
        self.from_value.valueChanged.connect(self.convert)
        ly.value_field(self.from_value)
        conv_grid.addWidget(self.from_value, 0, 1)

        self.from_unit = ly.choice_field(QComboBox(), min_width=120)
        self.from_unit.currentTextChanged.connect(self.convert)
        conv_grid.addWidget(self.from_unit, 0, 2)

        conv_grid.addWidget(ly.field_label("To"), 1, 0)
        self.to_value = QDoubleSpinBox()
        self.to_value.setRange(-1e10, 1e10)
        self.to_value.setDecimals(6)
        self.to_value.setReadOnly(True)
        self.to_value.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.to_value.setToolTip("The converted result. It is not editable.")
        ly.value_field(ly.read_only(self.to_value))
        conv_grid.addWidget(self.to_value, 1, 1)

        self.to_unit = ly.choice_field(QComboBox(), min_width=120)
        self.to_unit.currentTextChanged.connect(self.convert)
        conv_grid.addWidget(self.to_unit, 1, 2)

        conv_grid.setColumnStretch(1, 1)
        conv_section.addLayout(conv_grid)

        self.status_label = ly.status_label()
        conv_section.addWidget(self.status_label)
        layout.addLayout(conv_section)

        # Common conversions
        table_section = ly.vbox()
        table_section.addWidget(ly.heading("Common conversions"))
        self.conv_table = ly.results_table(
            ['From', 'To', 'Factor'],
            empty_text="No shorthand factors are listed for this property "
                       "type. The converter above still handles it.",
        )
        table_section.addWidget(self.conv_table)
        layout.addLayout(table_section, 1)

        # Initialize
        self.update_units()

        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def update_units(self):
        """Update available units based on property type"""
        prop_type = self.prop_type.currentText()
        units = _UNIT_MAP.get(prop_type, [])

        for combo in (self.from_unit, self.to_unit):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(units)
            combo.blockSignals(False)

        # Default to converting between two different units, not a no-op
        if len(units) > 1:
            self.to_unit.setCurrentIndex(1)

        self.update_conversion_table(prop_type)
        self.convert()

    def convert(self):
        """Perform unit conversion"""
        value = self.from_value.value()
        from_unit = self.from_unit.currentText()
        to_unit = self.to_unit.currentText()
        if not from_unit or not to_unit:
            return

        try:
            # Quantity() (not multiplication) is required for offset units
            # such as °C/°F, which pint refuses to multiply by a scalar.
            quantity = ureg.Quantity(value, from_unit)
            converted = quantity.to(to_unit)

            self.to_value.setValue(converted.magnitude)
            ly.set_status(self.status_label, "")

        except Exception as e:
            self.to_value.clear()
            ly.set_status(
                self.status_label,
                f"Cannot convert {from_unit} to {to_unit}: {e}", "error")

    def update_conversion_table(self, prop_type):
        """Update common conversions table"""
        conversions = _COMMON_CONVERSIONS.get(prop_type, [])
        ly.fill_table(self.conv_table, [list(row) for row in conversions])
