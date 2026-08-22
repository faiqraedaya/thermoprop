import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from CoolProp.CoolProp import PropsSI

from .sweeps import saturation_sweep, isobar_sweep, temperature_bounds

class PlotCanvas(FigureCanvas):
    """Matplotlib canvas for thermodynamic diagrams.

    All property sweeps come from core.sweeps; this class only draws.
    """

    def __init__(self, parent=None, width=12, height=8, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)

    def clear(self):
        """Clear the canvas."""
        self.fig.clear()
        self.axes = self.fig.add_subplot(111)
        self.draw()

    def plot_diagram(self, fluid, plot_type, show_grid=True, show_legend=True,
                    x_axis='Auto', y_axis='Auto'):
        """Plot generation with customization options"""
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

            self.fig.tight_layout()
            self.draw()

        except Exception as e:
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, f'Plot generation failed:\n{str(e)}',
                   transform=ax.transAxes, ha='center', va='center',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            self.draw()

    def _plot_ts_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Temperature-Entropy diagram"""
        ax = self.fig.add_subplot(111)
        sat = saturation_sweep(fluid, 100)
        ax.plot(sat['s_liq'] / 1000, sat['T'] - 273.15, 'b-',
                linewidth=2, label='Saturated Liquid')
        ax.plot(sat['s_vap'] / 1000, sat['T'] - 273.15, 'r-',
                linewidth=2, label='Saturated Vapor')
        ax.set_xlabel('Entropy (kJ/kg·K)')
        ax.set_ylabel('Temperature (°C)')
        ax.set_title(f'T-S Diagram for {fluid}')
        if show_grid:
            ax.grid(True, alpha=0.3)
        if show_legend:
            ax.legend()

    def _plot_hs_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Enthalpy-Entropy diagram"""
        ax = self.fig.add_subplot(111)
        Pc = PropsSI('Pcrit', fluid)
        sat = saturation_sweep(fluid, 100)

        ax.plot(sat['s_liq'] / 1000, sat['h_liq'] / 1000, 'b-',
               linewidth=2, label='Saturated Liquid')
        ax.plot(sat['s_vap'] / 1000, sat['h_vap'] / 1000, 'r-',
               linewidth=2, label='Saturated Vapor')

        # Add isobars
        pressures_bar = [0.1, 0.5, 1.0, 5.0, 10.0]
        for P in pressures_bar:
            if P * 1e5 < Pc:
                isobar = isobar_sweep(fluid, P * 1e5, 50)
                if np.count_nonzero(~np.isnan(isobar['h'])) > 5:
                    ax.plot(isobar['s'] / 1000, isobar['h'] / 1000,
                           '--', alpha=0.7, label=f'{P} bar')

        ax.set_xlabel('Entropy (kJ/kg·K)')
        ax.set_ylabel('Enthalpy (kJ/kg)')
        ax.set_title(f'H-S Diagram for {fluid}')

        if show_grid:
            ax.grid(True, alpha=0.3)
        if show_legend:
            ax.legend()

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

        # Clear the figure and create subplots
        self.fig.clear()
        ax1 = self.fig.add_subplot(221)
        ax2 = self.fig.add_subplot(222)
        ax3 = self.fig.add_subplot(223)
        ax4 = self.fig.add_subplot(224)

        T_C = T_range - 273.15

        ax1.plot(T_C, properties['Density'], 'b-', linewidth=2)
        ax1.set_ylabel('Density (kg/m³)')
        ax1.set_xlabel('Temperature (°C)')
        ax1.grid(show_grid, alpha=0.3)
        ax1.set_title('Density vs Temperature')

        ax2.plot(T_C, properties['Viscosity'], 'r-', linewidth=2)
        ax2.set_ylabel('Viscosity (mPa·s)')
        ax2.set_xlabel('Temperature (°C)')
        ax2.grid(show_grid, alpha=0.3)
        ax2.set_title('Viscosity vs Temperature')

        ax3.plot(T_C, properties['Thermal Conductivity'], 'g-', linewidth=2)
        ax3.set_ylabel('Thermal Conductivity (W/m·K)')
        ax3.set_xlabel('Temperature (°C)')
        ax3.grid(show_grid, alpha=0.3)
        ax3.set_title('Thermal Conductivity vs Temperature')

        ax4.plot(T_C, properties['Specific Heat (Cp)'], 'm-', linewidth=2)
        ax4.set_ylabel('Specific Heat Cp (kJ/kg·K)')
        ax4.set_xlabel('Temperature (°C)')
        ax4.grid(show_grid, alpha=0.3)
        ax4.set_title('Specific Heat vs Temperature')

        self.fig.suptitle(f'Property Variations for {fluid} at 1 atm')

    def _plot_property_vs_pressure(self, fluid, show_grid=True, show_legend=True):
        """Plot properties vs pressure at constant temperature (25 °C)"""
        P_range = np.logspace(3, 7, 100)  # 1 kPa to 10 MPa
        T_const = 298.15  # 25°C

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

        # Clear the figure and create subplots
        self.fig.clear()
        ax1 = self.fig.add_subplot(221)
        ax2 = self.fig.add_subplot(222)
        ax3 = self.fig.add_subplot(223)
        ax4 = self.fig.add_subplot(224)

        P_bar = np.array(P_valid) / 100000  # Convert to bar

        ax1.semilogx(P_bar, properties['Density'], 'b-', linewidth=2)
        ax1.set_ylabel('Density (kg/m³)')
        ax1.set_xlabel('Pressure (bar)')
        ax1.set_title('Density vs Pressure')
        if show_grid:
            ax1.grid(True, alpha=0.3)

        ax2.semilogx(P_bar, properties['Viscosity'], 'r-', linewidth=2)
        ax2.set_ylabel('Viscosity (mPa·s)')
        ax2.set_xlabel('Pressure (bar)')
        ax2.set_title('Viscosity vs Pressure')
        if show_grid:
            ax2.grid(True, alpha=0.3)

        ax3.semilogx(P_bar, properties['Thermal Conductivity'], 'g-', linewidth=2)
        ax3.set_ylabel('Thermal Conductivity (W/m·K)')
        ax3.set_xlabel('Pressure (bar)')
        ax3.set_title('Thermal Conductivity vs Pressure')
        if show_grid:
            ax3.grid(True, alpha=0.3)

        ax4.semilogx(P_bar, properties['Compressibility Factor'], 'm-', linewidth=2)
        ax4.set_ylabel('Compressibility Factor (-)')
        ax4.set_xlabel('Pressure (bar)')
        ax4.set_title('Compressibility Factor vs Pressure')
        ax4.axhline(y=1, color='k', linestyle='--', alpha=0.5, label='Ideal Gas')
        if show_grid:
            ax4.grid(True, alpha=0.3)
        if show_legend:
            ax4.legend()

        self.fig.suptitle(f'Property Variations for {fluid} at 25°C')

    def plot_process_path(self, results, process_type, fluid, show_grid=True, show_legend=True):
        """Plot process path results (arrays in SI)"""
        self.fig.clear()

        try:
            ax1 = self.fig.add_subplot(221)
            ax2 = self.fig.add_subplot(222)
            ax3 = self.fig.add_subplot(223)
            ax4 = self.fig.add_subplot(224)

            T_data = np.array(results['Temperature']) - 273.15  # Convert to °C
            P_data = np.array(results['Pressure']) / 100000     # Convert to bar

            # Remove NaN values
            valid_idx = ~(np.isnan(T_data) | np.isnan(P_data))
            T_valid = T_data[valid_idx]
            P_valid = P_data[valid_idx]

            # T-P diagram
            ax1.plot(T_valid, P_valid, 'b-', linewidth=2, marker='o', markersize=3)
            ax1.set_xlabel('Temperature (°C)')
            ax1.set_ylabel('Pressure (bar)')
            ax1.set_title(f'{process_type} Process - T-P Path')
            ax1.grid(show_grid, alpha=0.3)

            # Property evolution
            if 'Enthalpy' in results:
                H_data = np.array(results['Enthalpy'])[valid_idx] / 1000  # kJ/kg
                ax2.plot(T_valid, H_data, 'r-', linewidth=2, marker='s', markersize=3)
                ax2.set_xlabel('Temperature (°C)')
                ax2.set_ylabel('Enthalpy (kJ/kg)')
                ax2.set_title('Enthalpy vs Temperature')
                ax2.grid(show_grid, alpha=0.3)

            if 'Density' in results:
                rho_data = np.array(results['Density'])[valid_idx]
                ax3.plot(T_valid, rho_data, 'g-', linewidth=2, marker='^', markersize=3)
                ax3.set_xlabel('Temperature (°C)')
                ax3.set_ylabel('Density (kg/m³)')
                ax3.set_title('Density vs Temperature')
                ax3.grid(show_grid, alpha=0.3)

            if 'Entropy' in results:
                S_data = np.array(results['Entropy'])[valid_idx] / 1000  # kJ/kg/K
                ax4.plot(T_valid, S_data, 'm-', linewidth=2, marker='d', markersize=3)
                ax4.set_xlabel('Temperature (°C)')
                ax4.set_ylabel('Entropy (kJ/kg·K)')
                ax4.set_title('Entropy vs Temperature')
                ax4.grid(show_grid, alpha=0.3)

            self.fig.suptitle(f'{process_type} Process for {fluid}')
            self.fig.tight_layout()
            self.draw()

        except Exception as e:
            self.fig.clear()
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, f'Process plot failed:\n{str(e)}',
                   transform=ax.transAxes, ha='center', va='center')
            self.draw()

    def _plot_ph_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Pressure-Enthalpy diagram"""
        ax = self.fig.add_subplot(111)
        sat = saturation_sweep(fluid, 100)

        ax.plot(sat['h_liq'] / 1000, sat['P'] / 100000, 'b-',
               linewidth=2, label='Saturated Liquid')
        ax.plot(sat['h_vap'] / 1000, sat['P'] / 100000, 'r-',
               linewidth=2, label='Saturated Vapor')

        ax.set_xlabel('Enthalpy (kJ/kg)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title(f'P-H Diagram for {fluid}')
        ax.set_yscale('log')
        if show_legend:
            ax.legend()
        if show_grid:
            ax.grid(True, alpha=0.3)

    def _plot_pv_diagram(self, fluid, show_grid=True, show_legend=True):
        """Plot Pressure-Volume diagram"""
        ax = self.fig.add_subplot(111)
        sat = saturation_sweep(fluid, 50)

        with np.errstate(divide='ignore', invalid='ignore'):
            V_liq = 1.0 / sat['rho_liq']
            V_vap = 1.0 / sat['rho_vap']

        ax.plot(V_liq, sat['P'] / 100000, 'b-', linewidth=2, label='Saturated Liquid')
        ax.plot(V_vap, sat['P'] / 100000, 'r-', linewidth=2, label='Saturated Vapor')

        ax.set_xlabel('Specific Volume (m³/kg)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title(f'P-V Diagram for {fluid}')
        ax.set_xscale('log')
        ax.set_yscale('log')
        if show_legend:
            ax.legend()
        if show_grid:
            ax.grid(True, alpha=0.3)

    def _plot_saturation_curve(self, fluid, show_grid=True, show_legend=True):
        """Plot the saturation curve (P-T, density, etc.) for a pure fluid"""
        sat = saturation_sweep(fluid, 100)

        ax1 = self.fig.add_subplot(221)
        ax2 = self.fig.add_subplot(222)
        ax3 = self.fig.add_subplot(223)
        ax4 = self.fig.add_subplot(224)
        T_celsius = sat['T'] - 273.15
        P_bar = sat['P'] / 100000
        # T vs P
        ax1.semilogy(T_celsius, P_bar, 'b-', linewidth=2)
        ax1.set_xlabel('Temperature (°C)')
        ax1.set_ylabel('Pressure (bar)')
        ax1.set_title('Saturation Pressure vs Temperature')
        if show_grid:
            ax1.grid(True, alpha=0.3)
        # Density vs T
        ax2.plot(T_celsius, sat['rho_liq'], 'b-', linewidth=2, label='Liquid')
        ax2.plot(T_celsius, sat['rho_vap'], 'r-', linewidth=2, label='Vapor')
        ax2.set_xlabel('Temperature (°C)')
        ax2.set_ylabel('Density (kg/m³)')
        ax2.set_title('Saturation Density vs Temperature')
        if show_legend:
            ax2.legend()
        if show_grid:
            ax2.grid(True, alpha=0.3)
        # P-V diagram
        with np.errstate(divide='ignore', invalid='ignore'):
            V_liq = 1.0 / sat['rho_liq']
            V_vap = 1.0 / sat['rho_vap']
        ax3.loglog(V_liq, P_bar, 'b-', linewidth=2, label='Liquid')
        ax3.loglog(V_vap, P_bar, 'r-', linewidth=2, label='Vapor')
        ax3.set_xlabel('Specific Volume (m³/kg)')
        ax3.set_ylabel('Pressure (bar)')
        ax3.set_title('P-V Saturation Curve')
        if show_legend:
            ax3.legend()
        if show_grid:
            ax3.grid(True, alpha=0.3)
        # Density ratio
        with np.errstate(divide='ignore', invalid='ignore'):
            density_ratio = sat['rho_liq'] / sat['rho_vap']
        ax4.semilogy(T_celsius, density_ratio, 'g-', linewidth=2)
        ax4.set_xlabel('Temperature (°C)')
        ax4.set_ylabel('Density Ratio (ρ_liq/ρ_vap)')
        ax4.set_title('Liquid/Vapor Density Ratio')
        if show_grid:
            ax4.grid(True, alpha=0.3)
        self.fig.suptitle(f'Saturation Properties for {fluid}')

    def _plot_phase_envelope(self, fluid, show_grid=True, show_legend=True):
        """Plot the P-T phase diagram of a pure fluid with phase regions.

        Regions (melting line neglected — the liquid region extends to the
        left edge of the plot):
          Liquid:        T < Tc and P above the saturation curve
          Vapor/Gas:     P below the saturation curve, and T > Tc with P < Pc
          Supercritical: T > Tc and P > Pc
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
                        color='lightblue', alpha=0.3, label='Liquid')

        # Vapor/gas: below the saturation curve, and T > Tc below Pc
        ax.fill_between(T_plot, P_bot / 1e5, P_plot,
                        color='lightgreen', alpha=0.3, label='Vapor / Gas')
        T_ext = np.linspace(Tc, T_right, 50) - 273.15
        ax.fill_between(T_ext, P_bot / 1e5, np.full_like(T_ext, Pc / 1e5),
                        color='lightgreen', alpha=0.3)

        # Supercritical: T > Tc and P > Pc
        ax.fill_between(T_ext, np.full_like(T_ext, Pc / 1e5),
                        np.full_like(T_ext, P_top / 1e5),
                        color='lightyellow', alpha=0.5, label='Supercritical')

        # Saturation curve and critical point
        ax.semilogy(T_plot, P_plot, 'b-', linewidth=2, label='Saturation Curve')
        ax.plot(Tc_C, Pc / 1e5, 'ro', label='Critical Point')

        ax.set_xlabel('Temperature (°C)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title(f'Phase Diagram for {fluid} (melting line not shown)')
        if show_grid:
            ax.grid(True, alpha=0.3)
        if show_legend:
            ax.legend(loc='lower right')

        ax.set_xlim(Tt - 273.15, T_right - 273.15)
        ax.set_ylim(P_bot / 1e5, P_top / 1e5)

    def _plot_custom(self, fluid, x_axis, y_axis, show_grid=True, show_legend=True):
        """Plot a user-selected property on the x and y axes.

        Sweeps T at a fixed pressure of 1 atm (or sweeps P at a fixed
        temperature of 298.15 K when the x-axis is P); the held variable is
        stated in the plot title.
        """
        # Map axis names to CoolProp keys and labels
        axis_map = {
            'T': ('T', 'Temperature (°C)', lambda v: v - 273.15),
            'P': ('P', 'Pressure (bar)', lambda v: v / 100000),
            'H': ('H', 'Enthalpy (kJ/kg)', lambda v: v / 1000),
            'S': ('S', 'Entropy (kJ/kg·K)', lambda v: v / 1000),
            'D': ('D', 'Density (kg/m³)', lambda v: v),
            'V': ('V', 'Specific Volume (m³/kg)', lambda v: v),
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
            held_note = f'at T = {T_HELD:.2f} K'
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
            held_note = f'at P = 1 atm'
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
        ax.plot(x_plot, y_plot, 'b-', linewidth=2, label=f'{y_label} vs {x_label}')
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(f'{y_label} vs {x_label} for {fluid} ({held_note})')
        if show_grid:
            ax.grid(True, alpha=0.3)
        if show_legend:
            ax.legend()
