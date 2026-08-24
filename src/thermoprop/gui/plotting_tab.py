import io

from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QMessageBox, QWidget,
)

from .plot_canvas import PlotCanvas
from . import layout as ly
from .worker import host_window

_PLOT_TYPES = [
    'T-S Diagram', 'P-H Diagram', 'P-V Diagram', 'H-S Diagram',
    'Property vs Temperature', 'Property vs Pressure',
    'Saturation Curve', 'Phase Envelope', 'Custom Plot',
]

_AXES = ['Auto', 'T', 'P', 'H', 'S', 'D', 'V']


class PlottingTab(QWidget):
    def __init__(self, calc, parent=None):
        super().__init__(parent)
        self.calc = calc
        self.init_ui()

    def init_ui(self):
        """Plotting tab: plot controls on the left, the diagram on the right."""
        layout = ly.hbox(self, spacing=0)

        layout.addWidget(ly.splitter(
            self._build_control_panel(),
            self._build_plot_panel(),
            sizes=[340, 1060], stretch=[0, 1]))

    # -- Controls ---------------------------------------------------------

    def _build_control_panel(self) -> QWidget:
        panel, panel_layout = ly.panel()
        panel.setMinimumWidth(300)

        plot_section = ly.vbox()
        plot_section.addWidget(ly.heading("Diagram"))

        plot_form = ly.form()
        self.plot_fluid_combo = ly.choice_field(QComboBox())
        self.plot_fluid_combo.addItems(self.calc.fluids)
        self.plot_fluid_combo.setCurrentText('Water')
        plot_form.addRow(ly.field_label("Fluid"), self.plot_fluid_combo)

        self.plot_type_combo = ly.choice_field(QComboBox())
        self.plot_type_combo.addItems(_PLOT_TYPES)
        self.plot_type_combo.currentTextChanged.connect(self._update_axis_state)
        plot_form.addRow(ly.field_label("Diagram type"), self.plot_type_combo)
        plot_section.addLayout(plot_form)

        self.show_grid = QCheckBox("Show grid")
        self.show_grid.setChecked(True)
        plot_section.addWidget(self.show_grid)

        self.show_legend = QCheckBox("Show legend")
        self.show_legend.setChecked(True)
        self.show_legend.setToolTip(
            "The legend is how a reader tells the series apart. Hiding it "
            "leaves colour as the only cue.")
        plot_section.addWidget(self.show_legend)
        panel_layout.addLayout(plot_section)

        # Axes only apply to a custom plot, so they say so rather than
        # sitting there looking active.
        axes_section = ly.vbox()
        axes_section.addWidget(ly.heading("Custom axes"))
        self.axes_hint = ly.caption(
            "Used only by the Custom Plot diagram type.")
        axes_section.addWidget(self.axes_hint)

        axes_form = ly.form()
        self.x_axis_combo = ly.choice_field(QComboBox())
        self.x_axis_combo.addItems(_AXES)
        axes_form.addRow(ly.field_label("X axis"), self.x_axis_combo)

        self.y_axis_combo = ly.choice_field(QComboBox())
        self.y_axis_combo.addItems(_AXES)
        axes_form.addRow(ly.field_label("Y axis"), self.y_axis_combo)
        axes_section.addLayout(axes_form)
        panel_layout.addLayout(axes_section)

        self.plot_btn = ly.button("Generate plot", variant="primary",
                                  on_click=self.generate_plot)
        panel_layout.addLayout(ly.action_row(self.plot_btn))

        self.status = ly.status_label()
        panel_layout.addWidget(self.status)

        panel_layout.addStretch()

        # Export is its own action group, so neither button is primary
        export_section = ly.vbox()
        export_section.addWidget(ly.caption("Export"))
        export_row = ly.hbox()
        export_row.addWidget(ly.button("Save image...", on_click=self.save_plot))
        export_row.addWidget(ly.button("Copy plot", on_click=self.copy_plot))
        export_row.addStretch()
        export_section.addLayout(export_row)
        panel_layout.addLayout(export_section)

        self._update_axis_state(self.plot_type_combo.currentText())
        return panel

    def _build_plot_panel(self) -> QWidget:
        panel, panel_layout = ly.panel(spacing=8)
        panel.setMinimumWidth(400)
        self.plot_canvas = PlotCanvas(
            panel, width=12, height=8,
            empty_text="Pick a fluid and a diagram type, then choose "
                       "Generate plot.")
        panel_layout.addWidget(self.plot_canvas)
        return panel

    def _update_axis_state(self, plot_type: str):
        """Axis pickers are live only for the diagram type that reads them."""
        is_custom = (plot_type == 'Custom Plot')
        self.x_axis_combo.setEnabled(is_custom)
        self.y_axis_combo.setEnabled(is_custom)

    # -- Plotting ---------------------------------------------------------

    def generate_plot(self):
        """Generate plot based on configuration"""
        fluid = self.plot_fluid_combo.currentText()
        plot_type = self.plot_type_combo.currentText()

        ly.set_status(self.status, "")
        window = host_window(self)
        if window is not None:
            window.set_busy(True, f"Drawing the {plot_type} for {fluid}...")
        self.plot_btn.setEnabled(False)
        try:
            error = self.plot_canvas.plot_diagram(
                fluid,
                plot_type,
                show_grid=self.show_grid.isChecked(),
                show_legend=self.show_legend.isChecked(),
                x_axis=self.x_axis_combo.currentText(),
                y_axis=self.y_axis_combo.currentText(),
            )
        finally:
            self.plot_btn.setEnabled(True)
            if window is not None:
                window.set_busy(
                    False, "Plot generation failed" if error
                    else f"{plot_type} drawn for {fluid}")

        if error:
            ly.set_status(self.status, error, "error")

    def save_plot(self):
        """Save plot to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save plot", "",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)"
        )
        if filename:
            try:
                self.plot_canvas.figure.savefig(filename, dpi=150,
                                                bbox_inches='tight')
                window = host_window(self)
                if window is not None:
                    window.set_status(f"Plot saved: {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Save error",
                                     f"Failed to save plot: {str(e)}")

    def copy_plot(self):
        """Copy plot to clipboard as image"""
        try:
            buf = io.BytesIO()
            self.plot_canvas.figure.savefig(buf, format='png', dpi=150,
                                            bbox_inches='tight')
            buf.seek(0)
            img = QImage()
            img.loadFromData(buf.read())
            QApplication.clipboard().setImage(img)
            window = host_window(self)
            if window is not None:
                window.set_status("Plot copied to clipboard")
        except Exception as e:
            QMessageBox.critical(self, "Copy error",
                                 f"Failed to copy plot: {str(e)}")

    # -- Integration with main window (project / clear) -------------------

    def clear_data(self):
        """Clear the plot."""
        self.plot_canvas.clear()
        ly.set_status(self.status, "")

    def get_tab_data(self):
        """Serializable snapshot of the tab's inputs."""
        return {
            'fluid': self.plot_fluid_combo.currentText(),
            'plot_type': self.plot_type_combo.currentText(),
            'show_grid': self.show_grid.isChecked(),
            'show_legend': self.show_legend.isChecked(),
            'x_axis': self.x_axis_combo.currentText(),
            'y_axis': self.y_axis_combo.currentText(),
        }

    def load_tab_data(self, data):
        """Restore the tab's inputs from a snapshot."""
        if 'fluid' in data:
            self.plot_fluid_combo.setCurrentText(data['fluid'])
        if 'plot_type' in data:
            self.plot_type_combo.setCurrentText(data['plot_type'])
        if 'show_grid' in data:
            self.show_grid.setChecked(bool(data['show_grid']))
        if 'show_legend' in data:
            self.show_legend.setChecked(bool(data['show_legend']))
        if 'x_axis' in data:
            self.x_axis_combo.setCurrentText(data['x_axis'])
        if 'y_axis' in data:
            self.y_axis_combo.setCurrentText(data['y_axis'])
