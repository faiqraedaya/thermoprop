from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QTableWidget, QTableWidgetItem, QGroupBox, QDoubleSpinBox,
    QDialog, QDialogButtonBox,
)
import pint

# Initialize unit registry
ureg = pint.UnitRegistry()

class UnitConverterDialog(QDialog):
    """Unit conversion dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Unit Converter')
        self.setGeometry(300, 300, 500, 400)

        layout = QVBoxLayout(self)

        # Property type selection
        prop_layout = QHBoxLayout()
        prop_layout.addWidget(QLabel("Property Type:"))
        self.prop_type = QComboBox()
        self.prop_type.addItems([
            'Temperature', 'Pressure', 'Density', 'Energy', 'Power',
            'Length', 'Area', 'Volume', 'Mass', 'Force'
        ])
        self.prop_type.currentTextChanged.connect(self.update_units)
        prop_layout.addWidget(self.prop_type)
        layout.addLayout(prop_layout)

        # Conversion section
        conv_group = QGroupBox("Unit Conversion")
        conv_layout = QGridLayout(conv_group)

        # From
        conv_layout.addWidget(QLabel("From:"), 0, 0)
        self.from_value = QDoubleSpinBox()
        self.from_value.setRange(-1e10, 1e10)
        self.from_value.setDecimals(6)
        self.from_value.valueChanged.connect(self.convert)
        conv_layout.addWidget(self.from_value, 0, 1)

        self.from_unit = QComboBox()
        conv_layout.addWidget(self.from_unit, 0, 2)

        # To
        conv_layout.addWidget(QLabel("To:"), 1, 0)
        self.to_value = QDoubleSpinBox()
        self.to_value.setRange(-1e10, 1e10)
        self.to_value.setDecimals(6)
        self.to_value.setReadOnly(True)
        conv_layout.addWidget(self.to_value, 1, 1)

        self.to_unit = QComboBox()
        self.to_unit.currentTextChanged.connect(self.convert)
        conv_layout.addWidget(self.to_unit, 1, 2)

        # Conversion status/error display
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #b00020;")
        conv_layout.addWidget(self.status_label, 2, 0, 1, 3)

        layout.addWidget(conv_group)

        # Common conversions table
        table_group = QGroupBox("Common Conversions")
        table_layout = QVBoxLayout(table_group)

        self.conv_table = QTableWidget()
        self.conv_table.setColumnCount(3)
        self.conv_table.setHorizontalHeaderLabels(['From', 'To', 'Factor'])
        table_layout.addWidget(self.conv_table)

        layout.addWidget(table_group)

        # Initialize
        self.update_units()

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def update_units(self):
        """Update available units based on property type"""
        prop_type = self.prop_type.currentText()

        unit_map = {
            'Temperature': ['°C', 'K', '°F', '°R'],
            'Pressure': ['Pa', 'kPa', 'MPa', 'bar', 'psi', 'atm', 'mmHg', 'inHg'],
            'Density': ['kg/m³', 'g/cm³', 'lb/ft³', 'kg/L'],
            'Energy': ['J', 'kJ', 'MJ', 'cal', 'kcal', 'BTU', 'kWh'],
            'Power': ['W', 'kW', 'MW', 'hp', 'BTU/h'],
            'Length': ['m', 'cm', 'mm', 'km', 'in', 'ft', 'yd', 'mile'],
            'Area': ['m²', 'cm²', 'mm²', 'km²', 'in²', 'ft²', 'acre'],
            'Volume': ['m³', 'L', 'mL', 'cm³', 'in³', 'ft³', 'gal', 'qt'],
            'Mass': ['kg', 'g', 'mg', 'lb', 'oz', 'tonne'],
            'Force': ['N', 'kN', 'lbf', 'kgf', 'dyne']
        }

        units = unit_map.get(prop_type, [])

        self.from_unit.clear()
        self.from_unit.addItems(units)

        self.to_unit.clear()
        self.to_unit.addItems(units)

        self.update_conversion_table(prop_type)

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
            self.status_label.setText("")

        except Exception as e:
            self.to_value.clear()
            self.status_label.setText(
                f"Cannot convert {from_unit} → {to_unit}: {e}")

    def update_conversion_table(self, prop_type):
        """Update common conversions table"""
        common_conversions = {
            'Temperature': [
                ('°C', '°F', '×9/5 + 32'),
                ('°C', 'K', '+ 273.15'),
                ('°F', '°C', '(×-32)×5/9')
            ],
            'Pressure': [
                ('bar', 'psi', '× 14.504'),
                ('Pa', 'bar', '× 1e-5'),
                ('atm', 'Pa', '× 101325')
            ],
            'Energy': [
                ('J', 'cal', '× 0.239'),
                ('kWh', 'J', '× 3.6e6'),
                ('BTU', 'J', '× 1055')
            ]
        }

        conversions = common_conversions.get(prop_type, [])
        self.conv_table.setRowCount(len(conversions))

        for i, (from_u, to_u, factor) in enumerate(conversions):
            self.conv_table.setItem(i, 0, QTableWidgetItem(from_u))
            self.conv_table.setItem(i, 1, QTableWidgetItem(to_u))
            self.conv_table.setItem(i, 2, QTableWidgetItem(factor))

        self.conv_table.resizeColumnsToContents()
