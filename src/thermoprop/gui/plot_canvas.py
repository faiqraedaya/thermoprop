import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from CoolProp.CoolProp import PropsSI

from ..core.sweeps import saturation_sweep, isobar_sweep, temperature_bounds
from .theme import Tokens

# Chart chrome is neutral; only the data carries colour.
_INK = Tokens.ink_hex(Tokens.INK_PRIMARY)
_INK_SECONDARY = Tokens.ink_hex(Tokens.INK_SECONDARY)
_INK_TERTIARY = Tokens.ink_hex(Tokens.INK_TERTIARY)
_GLYPH = Tokens.ink_hex(Tokens.INK_GLYPH)

# Categorical identities, assigned in fixed slot order and never cycled.
_LIQUID = Tokens.series(0)
_VAPOUR = Tokens.series(1)
_SINGLE = Tokens.series(0)
_SUPERCRITICAL = Tokens.series(2)

# Region fills are the same hues at low alpha, so the saturation line on top
# of them stays the strongest mark in the figure.
_REGION_ALPHA = 0.16


class PlotCanvas(FigureCanvas):
    """Matplotlib canvas for thermodynamic diagrams.

    All property sweeps come from core.sweeps; this class only draws. Chart
    chrome follows the app's neutral palette (set globally by
    ``apply_mpl_theme``); data series use the validated categorical slots.
    """

    def __init__(self, parent=None, width=12, height=8, dpi=100,
                 empty_text: str = ""):
        # Constrained layout, not tight_layout: it accounts for the figure
        # title and keeps a 2x2 panel's axis labels from landing on the
        # title of the panel below it.
        self.fig = Figure(figsize=(width, height), dpi=dpi,
                          layout='constrained')
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setMinimumSize(320, 240)
        self.empty_text = empty_text
        if empty_text:
            self.show_message(empty_text)

    # -- Canvas states ----------------------------------------------------

    def clear(self):
        """Return the canvas to its empty state."""
        self.fig.clear()
        self.axes = self.fig.add_subplot(111)
        if self.empty_text:
            self.show_message(self.empty_text)
        else:
            self.draw()

    def show_message(self, text: str, tone: str = "neutral"):
        """Draw a single line of text instead of an empty white rectangle.

        An empty plot area gives the user nothing to act on; this says what
        will appear here, or what went wrong.
        """
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        self.axes = ax
        ax.axis('off')
        colour = Tokens.ERROR if tone == "error" else _INK_TERTIARY
        ax.text(0.5, 0.5, text, transform=ax.transAxes,
                ha='center', va='center', wrap=True,
                color=colour, fontsize=Tokens.pt(Tokens.FONT_CAPTION))
        self.draw()

    @staticmethod
    def _finish(ax, show_grid, show_legend, series_count):
        """Apply the shared axis treatment to a finished plot.

        A legend is present whenever two or more series share an axis - that
        is the only thing keeping identity from resting on colour alone. A
        lone series needs none; the title already names it.
        """
        if show_grid:
            ax.grid(True, color=Tokens.ink_hex(Tokens.SURFACE_BORDER),
                    linewidth=0.5)
        else:
            ax.grid(False)
        if show_legend and series_count >= 2:
            ax.legend(frameon=False, labelcolor=_INK_SECONDARY)

    # -- Entry point ------------------------------------------------------

    def plot_diagram(self, fluid, plot_type, show_grid=True, show_legend=True,
                    x_axis='Auto', y_axis='Auto'):
        """Draw one diagram. Returns an error message, or None on success."""
        self.fig.clear()

        try:
            if plot_type == 'T-S Diagram':
                self._plot_ts_diagram(fluid, show_grid, show_legend)
            elif plot_type == 'P-H Diagram':
                self._plot_ph_diagram(fluid, show_grid, show_legend)
            elif plot_type == 'P-V Diagram':
                self._plot_pv_diagram(fluid, show_grid, show_legend)
            elif plot_type == 'H-S Diagram':
                self._plot_hs_diagram(fluid, show_grid, show_legend)
            elif plot_type == 'Property vs Temperature':
                self._plot_property_vs_temp(fluid, show_grid, show_legend)
            elif plot_type == 'Property vs Pressure':
                self._plot_property_vs_pressure(fluid, show_grid, show_legend)
            elif plot_type == 'Saturation Curve':
                self._plot_saturation_curve(fluid, show_grid, show_legend)
            elif plot_type == 'Phase Envelope':
                self._plot_phase_envelope(fluid, show_grid, show_legend)
            elif plot_type == 'Custom Plot':
                self._plot_custom(fluid, x_axis, y_axis, show_grid, show_legend)

            self.draw()
            return None

        except Exception as e:
            message = f"Could not draw the {plot_type} for {fluid}: {e}"
            self.show_message(message, tone="error")
            return message

    # -- Pure-fluid diagrams ----------------------------------------------

    def _plot_ts_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Temperature-Entropy diagram"""
        ax = self.fig.add_subplot(111)
        sat = saturation_sweep(fluid, 100)
        ax.plot(sat['s_liq'] / 1000, sat['T'] - 273.15, color=_LIQUID,
                label='Saturated liquid')
        ax.plot(sat['s_vap'] / 1000, sat['T'] - 273.15, color=_VAPOUR,
                label='Saturated vapour')
        ax.set_xlabel('Entropy (kJ/kg·K)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_title(f'T-S diagram for {fluid}')
        self._finish(ax, show_grid, show_legend, 2)

    def _plot_hs_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Enthalpy-Entropy diagram"""
        ax = self.fig.add_subplot(111)
        Pc = PropsSI('Pcrit', fluid)
        sat = saturation_sweep(fluid, 100)

        ax.plot(sat['s_liq'] / 1000, sat['h_liq'] / 1000, color=_LIQUID,
                label='Saturated liquid')
        ax.plot(sat['s_vap'] / 1000, sat['h_vap'] / 1000, color=_VAPOUR,
                label='Saturated vapour')

        # The isobars are ordered reference contours, not identities. They
        # take a neutral ramp so they never compete with - or get mistaken
        # for - the two saturation series sharing these axes.
        pressures_bar = [0.1, 0.5, 1.0, 5.0, 10.0]
        drawn = 2
        for i, P in enumerate(pressures_bar):
            if P * 1e5 < Pc:
                isobar = isobar_sweep(fluid, P * 1e5, 50)
                if np.count_nonzero(~np.isnan(isobar['h'])) > 5:
                    ax.plot(isobar['s'] / 1000, isobar['h'] / 1000,
                            color=Tokens.sequential_ink(i, len(pressures_bar)),
                            linewidth=1.0, linestyle='--',
                            label=f'{P:g} bar isobar')
                    drawn += 1

        ax.set_xlabel('Entropy (kJ/kg·K)')
        ax.set_ylabel('Enthalpy (kJ/kg)')
        ax.set_title(f'H-S diagram for {fluid}')
        self._finish(ax, show_grid, show_legend, drawn)

    def _plot_ph_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Pressure-Enthalpy diagram"""
        ax = self.fig.add_subplot(111)
        sat = saturation_sweep(fluid, 100)

        ax.plot(sat['h_liq'] / 1000, sat['P'] / 100000, color=_LIQUID,
                label='Saturated liquid')
        ax.plot(sat['h_vap'] / 1000, sat['P'] / 100000, color=_VAPOUR,
                label='Saturated vapour')

        ax.set_xlabel('Enthalpy (kJ/kg)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title(f'P-H diagram for {fluid}')
        ax.set_yscale('log')
        self._finish(ax, show_grid, show_legend, 2)

    def _plot_pv_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Pressure-Volume diagram"""
        ax = self.fig.add_subplot(111)
        sat = saturation_sweep(fluid, 50)

        with np.errstate(divide='ignore', invalid='ignore'):
            V_liq = 1.0 / sat['rho_liq']
            V_vap = 1.0 / sat['rho_vap']

        ax.plot(V_liq, sat['P'] / 100000, color=_LIQUID,
                label='Saturated liquid')
        ax.plot(V_vap, sat['P'] / 100000, color=_VAPOUR,
                label='Saturated vapour')

        ax.set_xlabel('Specific volume (m³/kg)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title(f'P-V diagram for {fluid}')
        ax.set_xscale('log')
        ax.set_yscale('log')
        self._finish(ax, show_grid, show_legend, 2)

    # -- Small multiples ---------------------------------------------------

    def _plot_property_vs_temp(self, fluid, show_grid=True, show_legend=True):
        """Plot various properties vs temperature at constant pressure (1 atm)"""
        Tt, Tc = temperature_bounds(fluid)
        try:
            T_hi = min(1.5 * Tc, PropsSI('Tmax', fluid))
        except Exception:
            T_hi = 1.5 * Tc
        T_range = np.linspace(Tt, T_hi, 100)
        P_const = 101325  # 1 atm

        properties = {
            'Density': [],
            'Viscosity': [],
            'Thermal Conductivity': [],
            'Specific Heat (Cp)': []
        }

        for T in T_range:
            try:
                d = PropsSI('D', 'T', T, 'P', P_const, fluid)
                v = PropsSI('V', 'T', T, 'P', P_const, fluid) * 1000
                l = PropsSI('L', 'T', T, 'P', P_const, fluid)
                cp = PropsSI('Cpmass', 'T', T, 'P', P_const, fluid) / 1000
            except Exception:
                d = v = l = cp = np.nan
            properties['Density'].append(d)
            properties['Viscosity'].append(v)
            properties['Thermal Conductivity'].append(l)
            properties['Specific Heat (Cp)'].append(cp)

        self.fig.clear()
        T_C = T_range - 273.15

        # Small multiples: one series per panel, so one hue throughout. A
        # different colour per panel would encode nothing.
        panels = [
            ('Density', 'Density (kg/m³)', 'Density vs temperature'),
            ('Viscosity', 'Viscosity (mPa·s)', 'Viscosity vs temperature'),
            ('Thermal Conductivity', 'Thermal conductivity (W/m·K)',
             'Thermal conductivity vs temperature'),
            ('Specific Heat (Cp)', 'Specific heat Cp (kJ/kg·K)',
             'Specific heat vs temperature'),
        ]
        for i, (key, ylabel, title) in enumerate(panels, start=1):
            ax = self.fig.add_subplot(2, 2, i)
            ax.plot(T_C, properties[key], color=_SINGLE)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Temperature (°C)')
            ax.set_title(title)
            self._finish(ax, show_grid, show_legend, 1)

        self.fig.suptitle(f'Property variations for {fluid} at 1 atm',
                          color=_INK)

    def _plot_property_vs_pressure(self, fluid, show_grid=True, show_legend=True):
        """Plot properties vs pressure at constant temperature (25 °C)"""
        P_range = np.logspace(3, 7, 100)  # 1 kPa to 10 MPa
        T_const = 298.15  # 25 °C

        properties = {
            'Density': [],
            'Viscosity': [],
            'Thermal Conductivity': [],
            'Compressibility Factor': []
        }

        P_valid = []

        M = PropsSI('M', fluid)
        R = 8.314462618  # J/mol/K

        for P in P_range:
            try:
                rho = PropsSI('D', 'T', T_const, 'P', P, fluid)
                mu = PropsSI('V', 'T', T_const, 'P', P, fluid) * 1000  # mPa·s
                k = PropsSI('L', 'T', T_const, 'P', P, fluid)
                Z = P * M / (rho * R * T_const)

                properties['Density'].append(rho)
                properties['Viscosity'].append(mu)
                properties['Thermal Conductivity'].append(k)
                properties['Compressibility Factor'].append(Z)
                P_valid.append(P)

            except Exception:
                continue

        self.fig.clear()
        P_bar = np.array(P_valid) / 100000  # Convert to bar

        panels = [
            ('Density', 'Density (kg/m³)', 'Density vs pressure'),
            ('Viscosity', 'Viscosity (mPa·s)', 'Viscosity vs pressure'),
            ('Thermal Conductivity', 'Thermal conductivity (W/m·K)',
             'Thermal conductivity vs pressure'),
            ('Compressibility Factor', 'Compressibility factor (-)',
             'Compressibility factor vs pressure'),
        ]
        for i, (key, ylabel, title) in enumerate(panels, start=1):
            ax = self.fig.add_subplot(2, 2, i)
            ax.semilogx(P_bar, properties[key], color=_SINGLE)
            ax.set_ylabel(ylabel)
            ax.set_xlabel('Pressure (bar)')
            ax.set_title(title)
            if key == 'Compressibility Factor':
                # A reference line, not a data series, so it stays neutral
                # and is labelled in place rather than through the legend.
                ax.axhline(y=1, color=_GLYPH, linestyle='--', linewidth=1.0)
                ax.annotate('Ideal gas, Z = 1', xy=(0.98, 1.0),
                            xycoords=('axes fraction', 'data'),
                            xytext=(0, -5), textcoords='offset points',
                            ha='right', va='top',
                            color=_INK_TERTIARY,
                            fontsize=Tokens.pt(Tokens.FONT_CAPTION))
            self._finish(ax, show_grid, show_legend, 1)

        self.fig.suptitle(f'Property variations for {fluid} at 25 °C',
                          color=_INK)

    def _plot_saturation_curve(self, fluid, show_grid=True, show_legend=True):
        """Plot the saturation curve (P-T, density, etc.) for a pure fluid"""
        sat = saturation_sweep(fluid, 100)
        self._draw_saturation_panels(sat, fluid, show_grid, show_legend)

    def _draw_saturation_panels(self, sat, fluid, show_grid=True,
                                show_legend=True):
        """Four saturation views. `sat` is a sweep dict from core.sweeps."""
        ax1 = self.fig.add_subplot(221)
        ax2 = self.fig.add_subplot(222)
        ax3 = self.fig.add_subplot(223)
        ax4 = self.fig.add_subplot(224)

        T_celsius = sat['T'] - 273.15
        P_bar = sat['P'] / 100000

        ax1.semilogy(T_celsius, P_bar, color=_SINGLE)
        ax1.set_xlabel('Temperature (°C)')
        ax1.set_ylabel('Pressure (bar)')
        ax1.set_title('Saturation pressure vs temperature')
        self._finish(ax1, show_grid, show_legend, 1)

        ax2.plot(T_celsius, sat['rho_liq'], color=_LIQUID, label='Liquid')
        ax2.plot(T_celsius, sat['rho_vap'], color=_VAPOUR, label='Vapour')
        ax2.set_xlabel('Temperature (°C)')
        ax2.set_ylabel('Density (kg/m³)')
        ax2.set_title('Saturation density vs temperature')
        self._finish(ax2, show_grid, show_legend, 2)

        with np.errstate(divide='ignore', invalid='ignore'):
            V_liq = 1.0 / sat['rho_liq']
            V_vap = 1.0 / sat['rho_vap']
        ax3.loglog(V_liq, P_bar, color=_LIQUID, label='Liquid')
        ax3.loglog(V_vap, P_bar, color=_VAPOUR, label='Vapour')
        ax3.set_xlabel('Specific volume (m³/kg)')
        ax3.set_ylabel('Pressure (bar)')
        ax3.set_title('P-V saturation curve')
        self._finish(ax3, show_grid, show_legend, 2)

        with np.errstate(divide='ignore', invalid='ignore'):
            density_ratio = sat['rho_liq'] / sat['rho_vap']
        ax4.semilogy(T_celsius, density_ratio, color=_SINGLE)
        ax4.set_xlabel('Temperature (°C)')
        ax4.set_ylabel('Density ratio (liquid / vapour)')
        ax4.set_title('Liquid / vapour density ratio')
        self._finish(ax4, show_grid, show_legend, 1)

        self.fig.suptitle(f'Saturation properties for {fluid}', color=_INK)

    def plot_saturation_curve(self, sat, fluid, sat_type,
                              show_grid=True, show_legend=True):
        """Draw the saturation curve from an already-computed sweep.

        The sweep is done off the GUI thread; only the drawing happens here.
        """
        self.fig.clear()
        try:
            valid = ~np.isnan(sat['P'])
            if not valid.any():
                raise ValueError("no valid saturation states in this range")

            ax = self.fig.add_subplot(111)
            self.axes = ax
            T_C = sat['T'][valid] - 273.15
            P_bar = sat['P'][valid] / 1e5

            if sat_type == 'T':
                ax.semilogy(T_C, P_bar, color=_SINGLE)
                ax.set_xlabel('Temperature (°C)')
                ax.set_ylabel('Saturation pressure (bar)')
                ax.set_title(f'{fluid} saturation curve, P against T')
            else:
                ax.plot(P_bar, T_C, color=_SINGLE)
                ax.set_xscale('log')
                ax.set_xlabel('Saturation pressure (bar)')
                ax.set_ylabel('Temperature (°C)')
                ax.set_title(f'{fluid} saturation curve, T against P')

            self._finish(ax, show_grid, show_legend, 1)
            self.draw()
            return None
        except Exception as e:
            message = f"Could not draw the saturation curve for {fluid}: {e}"
            self.show_message(message, tone="error")
            return message

    # -- Process path ------------------------------------------------------

    def plot_process_path(self, results, process_type, fluid, show_grid=True,
                          show_legend=True):
        """Plot process path results (arrays in SI)"""
        self.fig.clear()

        try:
            T_data = np.array(results['Temperature']) - 273.15   # °C
            P_data = np.array(results['Pressure']) / 100000      # bar

            valid_idx = ~(np.isnan(T_data) | np.isnan(P_data))
            T_valid = T_data[valid_idx]
            P_valid = P_data[valid_idx]

            # One series per panel: small multiples, one hue.
            ax1 = self.fig.add_subplot(221)
            ax1.plot(T_valid, P_valid, color=_SINGLE, marker='o')
            ax1.set_xlabel('Temperature (°C)')
            ax1.set_ylabel('Pressure (bar)')
            ax1.set_title(f'{process_type} path, T against P')
            self._finish(ax1, show_grid, show_legend, 1)

            panels = [
                (222, 'Enthalpy', 1000, 'Enthalpy (kJ/kg)',
                 'Enthalpy vs temperature', 's'),
                (223, 'Density', 1, 'Density (kg/m³)',
                 'Density vs temperature', '^'),
                (224, 'Entropy', 1000, 'Entropy (kJ/kg·K)',
                 'Entropy vs temperature', 'd'),
            ]
            for position, key, scale, ylabel, title, marker in panels:
                if key not in results:
                    continue
                data = np.array(results[key])[valid_idx] / scale
                ax = self.fig.add_subplot(position)
                ax.plot(T_valid, data, color=_SINGLE, marker=marker)
                ax.set_xlabel('Temperature (°C)')
                ax.set_ylabel(ylabel)
                ax.set_title(title)
                self._finish(ax, show_grid, show_legend, 1)

            self.fig.suptitle(f'{process_type} process for {fluid}', color=_INK)
            self.draw()
            return None

        except Exception as e:
            message = f"Could not plot this process path: {e}"
            self.show_message(message, tone="error")
            return message

    # -- Phase envelope ----------------------------------------------------

    def _plot_phase_envelope(self, fluid, show_grid=True, show_legend=True):
        """Plot the P-T phase diagram of a pure fluid with phase regions.

        Regions (melting line neglected - the liquid region extends to the
        left edge of the plot):
          Liquid:        T < Tc and P above the saturation curve
          Vapour/Gas:    P below the saturation curve, and T > Tc with P < Pc
          Supercritical: T > Tc and P > Pc

        The three regions are an encoded value, so they keep their colour;
        each one also carries a text label inside the plot, because two of
        the three fills sit below 3:1 against the canvas and colour must
        never be the only cue.
        """
        Tc = PropsSI('Tcrit', fluid)
        Pc = PropsSI('Pcrit', fluid)
        sat = saturation_sweep(fluid, 200)

        valid = ~np.isnan(sat['P'])
        if not valid.any():
            raise ValueError(f"No valid saturation data for {fluid}")
        T_sat = sat['T'][valid]
        P_sat = sat['P'][valid]

        Tt = T_sat[0]
        P_bot = max(P_sat.min() * 0.5, 1e-3)
        P_top = Pc * 10

        ax = self.fig.add_subplot(111)

        T_plot = T_sat - 273.15
        P_plot = P_sat / 1e5
        Tc_C = Tc - 273.15
        T_right = Tc + 0.5 * (Tc - Tt)  # plot extends past Tc

        # Liquid: above the saturation curve, up to Tc
        ax.fill_between(T_plot, P_plot, P_top / 1e5,
                        color=_LIQUID, alpha=_REGION_ALPHA, linewidth=0,
                        label='Liquid')

        # Vapour/gas: below the saturation curve, and T > Tc below Pc
        ax.fill_between(T_plot, P_bot / 1e5, P_plot,
                        color=_VAPOUR, alpha=_REGION_ALPHA, linewidth=0,
                        label='Vapour / gas')
        T_ext = np.linspace(Tc, T_right, 50) - 273.15
        ax.fill_between(T_ext, P_bot / 1e5, np.full_like(T_ext, Pc / 1e5),
                        color=_VAPOUR, alpha=_REGION_ALPHA, linewidth=0)

        # Supercritical: T > Tc and P > Pc
        ax.fill_between(T_ext, np.full_like(T_ext, Pc / 1e5),
                        np.full_like(T_ext, P_top / 1e5),
                        color=_SUPERCRITICAL, alpha=_REGION_ALPHA,
                        linewidth=0, label='Supercritical')

        # Saturation curve and critical point
        ax.semilogy(T_plot, P_plot, color=_INK, linewidth=2,
                    label='Saturation curve')
        ax.plot(Tc_C, Pc / 1e5, marker='o', markersize=8, color=_INK,
                linestyle='none', label='Critical point')
        ax.annotate('Critical point',
                    xy=(Tc_C, Pc / 1e5), xytext=(-8, 8),
                    textcoords='offset points', ha='right', va='bottom',
                    color=_INK_SECONDARY, fontsize=Tokens.pt(Tokens.FONT_CAPTION))

        ax.set_xlabel('Temperature (°C)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title(f'Phase diagram for {fluid}')
        ax.set_xlim(Tt - 273.15, T_right - 273.15)
        ax.set_ylim(P_bot / 1e5, P_top / 1e5)

        # Direct labels inside each region: identity never rests on the fill
        # colour alone.
        self._label_region(ax, 0.18, 0.80, 'Liquid')
        self._label_region(ax, 0.45, 0.12, 'Vapour / gas')
        self._label_region(ax, 0.86, 0.86, 'Supercritical')

        self.fig.text(0.99, 0.01, 'Melting line not shown',
                      ha='right', va='bottom', color=_INK_TERTIARY,
                      fontsize=Tokens.pt(Tokens.FONT_CAPTION))

        if show_grid:
            ax.grid(True, color=Tokens.ink_hex(Tokens.SURFACE_BORDER),
                    linewidth=0.5)
        if show_legend:
            ax.legend(loc='lower right', frameon=False,
                      labelcolor=_INK_SECONDARY)

    @staticmethod
    def _label_region(ax, x, y, text):
        """Name a shaded region in place, in ink rather than in its own hue."""
        ax.text(x, y, text, transform=ax.transAxes, ha='center', va='center',
                color=_INK_SECONDARY, fontsize=Tokens.pt(Tokens.FONT_CAPTION),
                fontweight='medium')

    # -- Custom plot -------------------------------------------------------

    def _plot_custom(self, fluid, x_axis, y_axis, show_grid=True,
                     show_legend=True):
        """Plot a user-selected property on the x and y axes.

        Sweeps T at a fixed pressure of 1 atm (or sweeps P at a fixed
        temperature of 298.15 K when the x-axis is P); the held variable is
        stated in the plot title.
        """
        axis_map = {
            'T': ('T', 'Temperature (°C)', lambda v: v - 273.15),
            'P': ('P', 'Pressure (bar)', lambda v: v / 100000),
            'H': ('H', 'Enthalpy (kJ/kg)', lambda v: v / 1000),
            'S': ('S', 'Entropy (kJ/kg·K)', lambda v: v / 1000),
            'D': ('D', 'Density (kg/m³)', lambda v: v),
            'V': ('V', 'Specific volume (m³/kg)', lambda v: v),
        }
        # Default axes
        if x_axis == 'Auto':
            x_axis = 'T'
        if y_axis == 'Auto':
            y_axis = 'P'
        if x_axis not in axis_map or y_axis not in axis_map:
            raise ValueError('Invalid axis selection')
        x_key, x_label, x_conv = axis_map[x_axis]
        y_key, y_label, y_conv = axis_map[y_axis]

        P_HELD = 101325.0   # Pa, for T sweeps
        T_HELD = 298.15     # K, for P sweeps

        def props_at(t, p, key):
            if key == 'V':
                rho = PropsSI('D', 'T', t, 'P', p, fluid)
                return 1.0 / rho if rho > 0 else np.nan
            return PropsSI(key, 'T', t, 'P', p, fluid)

        if x_key == 'P':
            held_note = f'T held at {T_HELD:.2f} K'
            Pc = PropsSI('Pcrit', fluid)
            x_vals = np.logspace(4, np.log10(Pc * 0.99), 100)
            x_plot, y_plot = [], []
            for p in x_vals:
                try:
                    y = props_at(T_HELD, p, y_key)
                except Exception:
                    y = np.nan
                x_plot.append(x_conv(p))
                y_plot.append(y_conv(y) if not np.isnan(y) else np.nan)
        else:
            held_note = 'P held at 1 atm'
            Tt, Tc = temperature_bounds(fluid)
            t_vals = np.linspace(Tt, Tc * 0.99, 100)
            x_plot, y_plot = [], []
            for t in t_vals:
                try:
                    xv = t if x_key == 'T' else props_at(t, P_HELD, x_key)
                    yv = props_at(t, P_HELD, y_key)
                except Exception:
                    xv, yv = np.nan, np.nan
                x_plot.append(x_conv(xv) if not np.isnan(xv) else np.nan)
                y_plot.append(y_conv(yv) if not np.isnan(yv) else np.nan)

        ax = self.fig.add_subplot(111)
        # One series: the title names it, so no legend box is needed.
        ax.plot(x_plot, y_plot, color=_SINGLE)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(f'{y_label} against {x_label} for {fluid} ({held_note})')
        self._finish(ax, show_grid, show_legend, 1)
