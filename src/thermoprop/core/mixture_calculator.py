"""
Mixture calculator implementation for ThermoProp application

All inputs and outputs of the calculation methods are SI (K, Pa, J/kg, kg/m³)
unless a unit is stated in the returned (value, unit) tuple.
"""

import logging
from typing import Dict, List, Tuple, Optional

import numpy as np
import CoolProp.CoolProp as CP
from CoolProp.CoolProp import PropsSI, PhaseSI
from CoolProp.HumidAirProp import HAPropsSI

from .mixture_component import MixtureComponent

logger = logging.getLogger(__name__)

# Universal gas constant, J/kmol/K (CODATA); used with molar mass in kg/kmol.
R_UNIVERSAL = 8314.462618

# Input pairs supported by CoolProp's PropsSI for mass-based flash calculations,
# verified empirically against CoolProp 7.2.0 (PhaseSI flash succeeds).
# Unsupported among {T,P,H,D,S,U}: T-H, T-U, H-U, S-U.
SUPPORTED_INPUT_PAIRS = {
    frozenset(p) for p in [
        ('T', 'P'), ('T', 'D'), ('T', 'S'),
        ('P', 'H'), ('P', 'D'), ('P', 'S'), ('P', 'U'),
        ('H', 'D'), ('H', 'S'),
        ('D', 'S'), ('D', 'U'),
    ]
}

# Fluids acceptable in the Humid Air model besides water (dry-air constituents).
_AIR_CONSTITUENTS = {
    'air', 'nitrogen', 'n2', 'oxygen', 'o2', 'argon', 'ar',
    'co2', 'carbondioxide',
}

_LIQUID_LIKE_PHASES = {'liquid', 'twophase', 'supercritical_liquid'}


class MixtureCalculator:
    """Calculator for pure components and mixtures"""

    def __init__(self):
        """Initialize the mixture calculator"""
        self.fluids = self._get_available_fluids()
        self.mixture_models = ['Ideal Gas', 'Humid Air']

        # Common mixture systems
        self.predefined_mixtures = {
            'Air': [
                ('Nitrogen', 0.78084),
                ('Oxygen', 0.20946),
                ('Argon', 0.00934),
                ('CO2', 0.00036)
            ],
            'Natural Gas (Typical)': [
                ('Methane', 0.85),
                ('Ethane', 0.10),
                ('Propane', 0.03),
                ('n-Butane', 0.015),
                ('CO2', 0.005)
            ],
            'Flue Gas (Coal)': [
                ('CO2', 0.12),
                ('H2O', 0.08),
                ('Nitrogen', 0.75),
                ('Oxygen', 0.05)
            ]
        }

    def _get_available_fluids(self) -> List[str]:
        """
        Get comprehensive list of available fluids

        Returns:
            List of available fluid names
        """
        try:
            fluid_list = CP.get_global_param_string("FluidsList").split(',')

            # Add common fluids and aliases
            common_fluids = [
                'Water', 'Air', 'Nitrogen', 'Oxygen', 'CO2', 'Methane', 'Ethane',
                'Propane', 'n-Butane', 'i-Butane', 'n-Pentane', 'i-Pentane',
                'Ammonia', 'R134a', 'R410A', 'R22', 'R404A', 'R407C', 'R32',
                'Hydrogen', 'Helium', 'Argon', 'Benzene', 'Toluene', 'Ethanol',
                'Acetone', 'CarbonMonoxide', 'SulfurDioxide', 'HydrogenSulfide'
            ]

            all_fluids = list(set(fluid_list + common_fluids))
            all_fluids.sort()
            return all_fluids
        except Exception as e:
            logger.warning("Failed to get fluid list: %s", e)
            # Fallback list
            return ['Water', 'Air', 'Nitrogen', 'Oxygen', 'CO2', 'Methane', 'Propane']

    def calculate_mixture_properties(
        self,
        components: List[MixtureComponent],
        T: float,
        P: float,
        model: str = 'Ideal Gas'
    ) -> Tuple[Optional[Dict[str, Tuple[float, str]]], Optional[str]]:
        """
        Calculate mixture properties using specified model

        Args:
            components: List of mixture components
            T: Temperature in K
            P: Pressure in Pa
            model: Mixture model to use ('Ideal Gas' or 'Humid Air')

        Returns:
            Tuple of (results dictionary, error message if any).
            The model is never switched silently: a failure in the requested
            model is returned as an error.
        """
        if not components:
            return None, "No components provided"

        if model not in self.mixture_models:
            return None, f"Invalid model: {model}"

        if T <= 0:
            return None, f"Temperature must be above absolute zero (got {T} K)"
        if P <= 0:
            return None, f"Pressure must be positive (got {P} Pa)"

        try:
            if model == 'Humid Air':
                return self._calculate_humid_air(components, T, P)
            else:
                return self._calculate_ideal_gas_mixture(components, T, P)

        except Exception as e:
            return None, f"Calculation error: {str(e)}"

    def _calculate_ideal_gas_mixture(
        self,
        components: List[MixtureComponent],
        T: float,
        P: float
    ) -> Tuple[Dict[str, Tuple[float, str]], None]:
        """
        Calculate mixture properties using ideal (Gibbs–Dalton) mixing rules.

        Each component is evaluated in the gas phase at its partial pressure
        x_i·P, so enthalpy and entropy include the ideal entropy of mixing and
        reduce exactly to the pure-fluid values for a single component.
        Viscosity uses Wilke's rule; thermal conductivity uses the
        Wassiljewa equation with the Mason–Saxena approximation A_ij ≈ φ_ij.

        Raises:
            ValueError: If total mole fraction is zero, if any component is
                below its dew point at its partial pressure (the model is not
                valid there), or if a component's thermodynamic properties
                cannot be evaluated.
        """
        results: Dict[str, Tuple[float, str]] = {}

        active = [comp for comp in components if comp.mole_fraction > 0]
        total_moles = sum(comp.mole_fraction for comp in active)
        if total_moles <= 0:
            raise ValueError("Total mole fractions cannot be zero")

        x = [comp.mole_fraction / total_moles for comp in active]
        M = [comp.molecular_weight for comp in active]  # g/mol == kg/kmol

        M_mix = sum(xi * Mi for xi, Mi in zip(x, M))
        results['Molar Mass'] = (M_mix / 1000, 'kg/mol')

        # Mixture density (ideal gas law)
        rho_mix = (P * M_mix) / (R_UNIVERSAL * T)
        results['Density'] = (rho_mix, 'kg/m³')

        w = [xi * Mi / M_mix for xi, Mi in zip(x, M)]  # mass fractions

        cp_i, cv_i, h_i, s_i = [], [], [], []
        mu_i, k_i = [], []

        for comp, xi in zip(active, x):
            P_partial = xi * P

            # The ideal-gas model is only valid if every component is a gas at
            # its partial pressure; otherwise it would (wrongly) mix in
            # liquid-phase properties.
            try:
                phase = PhaseSI('T', T, 'P', P_partial, comp.name)
            except Exception as e:
                raise ValueError(
                    f"Cannot evaluate '{comp.name}' at T={T:.2f} K and partial "
                    f"pressure {P_partial:.4g} Pa: {e}"
                ) from e
            if phase in _LIQUID_LIKE_PHASES:
                raise ValueError(
                    f"'{comp.name}' is below its dew point at these conditions "
                    f"(partial pressure {P_partial:.4g} Pa is at or above its "
                    f"saturation pressure at {T:.2f} K, phase: {phase}). "
                    f"The ideal-gas mixing model is not valid here; raise the "
                    f"temperature or reduce the {comp.name} fraction."
                )

            try:
                cp_i.append(PropsSI('Cpmass', 'T', T, 'P', P_partial, comp.name))
                cv_i.append(PropsSI('Cvmass', 'T', T, 'P', P_partial, comp.name))
                h_i.append(PropsSI('H', 'T', T, 'P', P_partial, comp.name))
                s_i.append(PropsSI('S', 'T', T, 'P', P_partial, comp.name))
            except Exception as e:
                raise ValueError(
                    f"Failed to calculate thermodynamic properties for "
                    f"'{comp.name}' at T={T:.2f} K, P={P_partial:.4g} Pa: {e}"
                ) from e

            # Transport correlations are missing for some CoolProp fluids;
            # report NaN for the mixture rather than failing the whole
            # calculation.
            try:
                mu_i.append(PropsSI('V', 'T', T, 'P', P_partial, comp.name))
            except Exception:
                logger.warning("No viscosity model for %s; mixture viscosity "
                               "will be reported as N/A", comp.name)
                mu_i.append(float('nan'))
            try:
                k_i.append(PropsSI('L', 'T', T, 'P', P_partial, comp.name))
            except Exception:
                logger.warning("No thermal-conductivity model for %s; mixture "
                               "conductivity will be reported as N/A", comp.name)
                k_i.append(float('nan'))

        Cp_mix = sum(wi * cpi for wi, cpi in zip(w, cp_i))
        Cv_mix = sum(wi * cvi for wi, cvi in zip(w, cv_i))
        results['Isobaric Heat Capacity'] = (Cp_mix, 'J/kg/K')
        results['Isochoric Heat Capacity'] = (Cv_mix, 'J/kg/K')

        results['Viscosity'] = (self._wilke_mix(x, mu_i, M), 'Pa·s')
        results['Thermal Conductivity'] = (
            self._wassiljewa_mix(x, k_i, mu_i, M), 'W/m/K')

        gamma = Cp_mix / Cv_mix
        a_mix = np.sqrt(gamma * R_UNIVERSAL * T / M_mix)
        results['Speed of Sound'] = (a_mix, 'm/s')

        results['Compressibility Factor'] = (1.0, '- (ideal-gas assumption)')

        # Gibbs–Dalton: mass-weighted component values at partial pressure.
        # Component reference states are CoolProp's per-fluid defaults, so
        # absolute values carry an arbitrary composition-dependent offset;
        # differences along a path at fixed composition are meaningful.
        h_mix = sum(wi * hi for wi, hi in zip(w, h_i))
        s_mix = sum(wi * si for wi, si in zip(w, s_i))
        results['Enthalpy'] = (h_mix, 'J/kg')
        results['Entropy'] = (s_mix, 'J/kg/K')

        return results, None

    @staticmethod
    def _wilke_phi(x, mu, M):
        """Wilke interaction parameters φ_ij from viscosities and molar masses."""
        n = len(x)
        phi = [[1.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                phi[i][j] = ((1 + (mu[i] / mu[j]) ** 0.5 * (M[j] / M[i]) ** 0.25) ** 2
                             / (8 * (1 + M[i] / M[j])) ** 0.5)
        return phi

    @classmethod
    def _wilke_mix(cls, x, mu, M) -> float:
        """Mixture viscosity by Wilke's rule; NaN if any component is missing."""
        if any(np.isnan(v) for v in mu):
            return float('nan')
        phi = cls._wilke_phi(x, mu, M)
        return sum(
            x[i] * mu[i] / sum(x[j] * phi[i][j] for j in range(len(x)))
            for i in range(len(x))
        )

    @classmethod
    def _wassiljewa_mix(cls, x, k, mu, M) -> float:
        """
        Mixture thermal conductivity by the Wassiljewa equation with the
        Mason–Saxena approximation A_ij ≈ φ_ij (Wilke's φ from viscosities).
        Falls back to a mole-fraction average if viscosities are unavailable.
        """
        if any(np.isnan(v) for v in k):
            return float('nan')
        if any(np.isnan(v) for v in mu):
            return sum(xi * ki for xi, ki in zip(x, k))
        phi = cls._wilke_phi(x, mu, M)
        return sum(
            x[i] * k[i] / sum(x[j] * phi[i][j] for j in range(len(x)))
            for i in range(len(x))
        )

    def _calculate_humid_air(
        self,
        components: List[MixtureComponent],
        T: float,
        P: float
    ) -> Tuple[Dict[str, Tuple[float, str]], None]:
        """
        Calculate humid air properties via CoolProp HAPropsSI (ASHRAE RP-1485).

        All reported specific properties use the per-kg-of-humid-air basis
        ('Hha'/'Sha'/'Vha' keys), so density, enthalpy and entropy are on a
        consistent basis.

        Raises:
            ValueError: If the composition contains non-air constituents, or
                if the state is supersaturated (RH > 1).
        """
        total_moles = sum(comp.mole_fraction for comp in components)
        if total_moles <= 0:
            raise ValueError("Total mole fractions cannot be zero")

        water_fraction = 0.0
        for comp in components:
            frac = comp.mole_fraction / total_moles
            name = comp.name.lower()
            if name in ('water', 'h2o'):
                water_fraction += frac
            elif frac > 0 and name not in _AIR_CONSTITUENTS:
                raise ValueError(
                    f"The Humid Air model is only valid for water plus dry-air "
                    f"constituents (N2, O2, Ar, CO2); '{comp.name}' is not "
                    f"supported. Use the Ideal Gas model instead."
                )

        # RH = p_w / p_ws(T) with p_w = y_w·P (enhancement factor neglected)
        P_ws = PropsSI('P', 'T', T, 'Q', 0, 'Water')
        P_w = water_fraction * P
        RH = P_w / P_ws
        if RH > 1.0 + 1e-9:
            raise ValueError(
                f"Mixture is supersaturated: water partial pressure "
                f"{P_w:.4g} Pa exceeds the saturation pressure {P_ws:.4g} Pa "
                f"at {T:.2f} K (RH = {RH * 100:.1f}%). Reduce the water "
                f"fraction or increase the temperature."
            )
        RH = min(RH, 1.0)

        results: Dict[str, Tuple[float, str]] = {}
        results['Density'] = (
            1.0 / HAPropsSI('Vha', 'T', T, 'P', P, 'R', RH), 'kg/m³')
        results['Enthalpy'] = (
            HAPropsSI('Hha', 'T', T, 'P', P, 'R', RH), 'J/kg humid air')
        results['Entropy'] = (
            HAPropsSI('Sha', 'T', T, 'P', P, 'R', RH), 'J/kg humid air/K')
        results['Relative Humidity'] = (RH * 100, '%')
        results['Humidity Ratio'] = (
            HAPropsSI('W', 'T', T, 'P', P, 'R', RH), 'kg water/kg dry air')
        results['Dew Point'] = (
            HAPropsSI('Tdp', 'T', T, 'P', P, 'R', RH), 'K')

        return results, None

    def calculate_saturation_properties(
        self,
        fluid: str,
        sat_type: str,
        sat_value: float,
        sat_unit: str
    ) -> Dict[str, Tuple[float, str]]:
        """
        Calculate saturation properties.

        For pseudo-pure fluids (e.g. Air, R404A) the bubble and dew points
        differ and are reported separately; the liquid branch is evaluated at
        Q=0 and the vapor branch at Q=1 of the given input.

        Args:
            fluid: Fluid name
            sat_type: Saturation type ('T' for temperature or 'P' for pressure)
            sat_value: Saturation value
            sat_unit: Unit of the saturation value

        Returns:
            Dictionary of saturation properties

        Raises:
            ValueError: If invalid saturation type/unit or the state is
                outside the saturation region (e.g. above the critical point)
        """
        try:
            results: Dict[str, Tuple[float, str]] = {}

            if sat_type == 'T':
                temp_si = self._convert_to_si(sat_value, sat_unit, 'T')
                Tc = PropsSI('Tcrit', fluid)
                if temp_si >= Tc:
                    raise ValueError(
                        f"Temperature {temp_si:.2f} K is at or above the "
                        f"critical temperature of {fluid} ({Tc:.2f} K); no "
                        f"saturation state exists.")
                p_bubble = PropsSI('P', 'T', temp_si, 'Q', 0, fluid)
                p_dew = PropsSI('P', 'T', temp_si, 'Q', 1, fluid)
                results['Saturation Temperature'] = (temp_si, 'K')
                if abs(p_dew - p_bubble) > 1e-6 * max(p_bubble, 1e-12):
                    results['Saturation Pressure (bubble)'] = (p_bubble, 'Pa')
                    results['Saturation Pressure (dew)'] = (p_dew, 'Pa')
                else:
                    results['Saturation Pressure'] = (p_bubble, 'Pa')
                in_name, in_val = 'T', temp_si
            elif sat_type == 'P':
                pres_si = self._convert_to_si(sat_value, sat_unit, 'P')
                Pc = PropsSI('Pcrit', fluid)
                if pres_si >= Pc:
                    raise ValueError(
                        f"Pressure {pres_si:.4g} Pa is at or above the "
                        f"critical pressure of {fluid} ({Pc:.4g} Pa); no "
                        f"saturation state exists.")
                t_bubble = PropsSI('T', 'P', pres_si, 'Q', 0, fluid)
                t_dew = PropsSI('T', 'P', pres_si, 'Q', 1, fluid)
                results['Saturation Pressure'] = (pres_si, 'Pa')
                if abs(t_dew - t_bubble) > 1e-6 * max(t_bubble, 1e-12):
                    results['Saturation Temperature (bubble)'] = (t_bubble, 'K')
                    results['Saturation Temperature (dew)'] = (t_dew, 'K')
                else:
                    results['Saturation Temperature'] = (t_bubble, 'K')
                in_name, in_val = 'P', pres_si
            else:
                raise ValueError(f"Invalid saturation type: {sat_type}")

            h_liq = PropsSI('H', in_name, in_val, 'Q', 0, fluid)
            h_vap = PropsSI('H', in_name, in_val, 'Q', 1, fluid)
            results.update({
                'Liquid Density': (PropsSI('D', in_name, in_val, 'Q', 0, fluid), 'kg/m³'),
                'Vapor Density': (PropsSI('D', in_name, in_val, 'Q', 1, fluid), 'kg/m³'),
                'Liquid Enthalpy': (h_liq, 'J/kg'),
                'Vapor Enthalpy': (h_vap, 'J/kg'),
                'Liquid Entropy': (PropsSI('S', in_name, in_val, 'Q', 0, fluid), 'J/kg/K'),
                'Vapor Entropy': (PropsSI('S', in_name, in_val, 'Q', 1, fluid), 'J/kg/K'),
                'Latent Heat': (h_vap - h_liq, 'J/kg'),
            })

            return results

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to calculate saturation properties: {str(e)}") from e

    def _convert_to_si(self, value: float, unit: str, prop_type: str) -> float:
        """
        Convert a value to SI units

        Args:
            value: Value to convert
            unit: Current unit
            prop_type: Property type ('T', 'P', 'H', 'U', 'D', 'S')

        Returns:
            Value in SI units

        Raises:
            ValueError: If invalid unit or property type, or if the result is
                unphysical (T ≤ 0 K, P ≤ 0 Pa)
        """
        if prop_type == 'T':
            if unit == 'K':
                result = value
            elif unit in ['°C', 'C']:
                result = value + 273.15
            elif unit in ['°F', 'F']:
                result = (value - 32) * 5 / 9 + 273.15
            else:
                raise ValueError(f"Invalid temperature unit: {unit}")
            if result <= 0:
                raise ValueError(
                    f"Temperature {value} {unit} is at or below absolute zero")
            return result
        elif prop_type == 'P':
            if unit == 'Pa':
                result = value
            elif unit == 'kPa':
                result = value * 1000
            elif unit == 'MPa':
                result = value * 1e6
            elif unit in ('bar', 'bara'):
                result = value * 1e5
            elif unit == 'barg':
                result = (value + 1.01325) * 1e5
            elif unit == 'atm':
                result = value * 101325
            elif unit in ('psi', 'psia'):
                result = value * 6894.76
            elif unit == 'psig':
                result = (value + 14.696) * 6894.76
            else:
                raise ValueError(f"Invalid pressure unit: {unit}")
            if result <= 0:
                raise ValueError(
                    f"Pressure {value} {unit} is not above absolute vacuum")
            return result
        elif prop_type in ('H', 'U'):
            if unit == 'J/kg':
                return value
            elif unit == 'kJ/kg':
                return value * 1000
            elif unit == 'MJ/kg':
                return value * 1e6
            elif unit == 'BTU/lb':
                return value * 2326.0
            else:
                raise ValueError(f"Invalid {prop_type} unit: {unit}")
        elif prop_type == 'D':
            if unit == 'kg/m³':
                return value
            elif unit == 'g/cm³':
                return value * 1000
            elif unit == 'lb/ft³':
                return value * 16.0185
            elif unit == 'kg/L':
                return value * 1000
            else:
                raise ValueError(f"Invalid density unit: {unit}")
        elif prop_type == 'S':
            if unit == 'J/kg/K':
                return value
            elif unit == 'kJ/kg/K':
                return value * 1000
            else:
                raise ValueError(f"Invalid entropy unit: {unit}")
        else:
            raise ValueError(f"Invalid property type: {prop_type}")

    def calculate_single_point_properties(
        self,
        fluid: str,
        prop1: str,
        prop1_value: float,
        prop1_unit: str,
        prop2: str,
        prop2_value: float,
        prop2_unit: str
    ) -> Dict[str, Tuple[float, str]]:
        """
        Calculate single point properties for a pure fluid

        Args:
            fluid: Fluid name
            prop1: First property type ('T', 'P', 'H', 'D', 'S', 'U')
            prop1_value: First property value
            prop1_unit: First property unit
            prop2: Second property type ('T', 'P', 'H', 'D', 'S', 'U')
            prop2_value: Second property value
            prop2_unit: Second property unit

        Returns:
            Dictionary of calculated properties

        Raises:
            ValueError: If the input pair is unsupported, properties are
                invalid, or the calculation fails
        """
        valid_props = {'T', 'P', 'H', 'D', 'S', 'U'}
        if prop1 not in valid_props or prop2 not in valid_props:
            raise ValueError(f"Invalid property types: {prop1}, {prop2}")
        if prop1 == prop2:
            raise ValueError("The two input properties must be different")
        if frozenset((prop1, prop2)) not in SUPPORTED_INPUT_PAIRS:
            supported = sorted('+'.join(sorted(p)) for p in SUPPORTED_INPUT_PAIRS)
            raise ValueError(
                f"The input pair {prop1}+{prop2} is not supported by CoolProp. "
                f"Supported pairs: {', '.join(supported)}")

        try:
            # Convert inputs to SI units
            prop1_si = self._convert_to_si(prop1_value, prop1_unit, prop1)
            prop2_si = self._convert_to_si(prop2_value, prop2_unit, prop2)

            # Helper to safely get properties
            def safe_props_si(prop, unit):
                try:
                    val = PropsSI(prop, prop1, prop1_si, prop2, prop2_si, fluid)
                    return (val, unit)
                except Exception:
                    return (np.nan, unit)

            # Calculate all properties using CoolProp
            results = {}

            # Basic properties
            results['Temperature'] = safe_props_si('T', 'K')
            results['Pressure'] = safe_props_si('P', 'Pa')
            results['Density'] = safe_props_si('D', 'kg/m³')
            results['Enthalpy'] = safe_props_si('H', 'J/kg')
            results['Entropy'] = safe_props_si('S', 'J/kg/K')
            results['Internal Energy'] = safe_props_si('U', 'J/kg')

            # Heat capacities
            results['Isobaric Heat Capacity'] = safe_props_si('Cpmass', 'J/kg/K')
            results['Isochoric Heat Capacity'] = safe_props_si('Cvmass', 'J/kg/K')

            # Transport properties
            results['Viscosity'] = safe_props_si('V', 'Pa·s')
            results['Thermal Conductivity'] = safe_props_si('L', 'W/m/K')

            # Other properties
            results['Speed of Sound'] = safe_props_si('A', 'm/s')
            results['Surface Tension'] = safe_props_si('I', 'N/m')

            # CoolProp returns Q = -1 for states outside the two-phase region;
            # report those as N/A rather than a fictitious quality.
            q_val, q_unit = safe_props_si('Q', '-')
            if not (0.0 <= q_val <= 1.0):
                q_val = np.nan
            results['Quality'] = (q_val, q_unit)

            # Phase information
            try:
                phase = PhaseSI(prop1, prop1_si, prop2, prop2_si, fluid)
                if phase.startswith('unknown'):
                    phase = 'Unknown'
                results['Phase'] = (phase, '-')
            except Exception:
                results['Phase'] = ('Unknown', '-')

            # Molar properties
            results['Molar Mass'] = safe_props_si('M', 'kg/mol')
            results['Molar Enthalpy'] = safe_props_si('Hmolar', 'J/mol')
            results['Molar Entropy'] = safe_props_si('Smolar', 'J/mol/K')

            return results

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to calculate properties: {str(e)}") from e

    # ------------------------------------------------------------------
    # Process path simulation
    # ------------------------------------------------------------------

    _PATH_KEYS = ('Temperature', 'Pressure', 'Enthalpy', 'Entropy',
                  'Density', 'Internal Energy', 'Quality')

    @staticmethod
    def _path_state(fluid: str, name1: str, val1: float,
                    name2: str, val2: float) -> dict:
        """
        Evaluate one state point along a path from an input pair.
        Returns a row dict with SI values; NaN entries on failure.
        """
        row = {key: float('nan') for key in MixtureCalculator._PATH_KEYS}
        row['Phase'] = 'Unknown'
        try:
            row['Temperature'] = PropsSI('T', name1, val1, name2, val2, fluid)
            row['Pressure'] = PropsSI('P', name1, val1, name2, val2, fluid)
            row['Enthalpy'] = PropsSI('H', name1, val1, name2, val2, fluid)
            row['Entropy'] = PropsSI('S', name1, val1, name2, val2, fluid)
            row['Density'] = PropsSI('D', name1, val1, name2, val2, fluid)
            row['Internal Energy'] = PropsSI('U', name1, val1, name2, val2, fluid)
            q = PropsSI('Q', name1, val1, name2, val2, fluid)
            row['Quality'] = q if 0.0 <= q <= 1.0 else float('nan')
        except Exception:
            return row
        try:
            phase = PhaseSI(name1, val1, name2, val2, fluid)
            row['Phase'] = 'Unknown' if phase.startswith('unknown') else phase
        except Exception:
            if 'Q' in (name1, name2):
                row['Phase'] = 'twophase'
        return row

    @staticmethod
    def _two_phase_pairs(anchor_name: str, anchor_val: float,
                         q_start: float, q_end: float, n: int) -> list:
        """Input pairs spanning the two-phase dome at a fixed T or P."""
        return [(anchor_name, anchor_val, 'Q', q)
                for q in np.linspace(q_start, q_end, n)]

    def simulate_process_path(
        self,
        fluid: str,
        process_type: str,
        initial_T: float,
        initial_P: float,
        final_value: float,
        num_points: int = 50,
        polytropic_n: float = 1.3  # Only used for polytropic
    ) -> dict:
        """
        Simulate a process path for a pure fluid. All values are SI.

        Process definitions:
            Isobaric:    dP = 0, sweep T; two-phase segment inserted at T_sat
            Isochoric:   dv = 0, sweep T at constant density (real-fluid)
            Isothermal:  dT = 0, sweep P; two-phase segment inserted at P_sat
            Isenthalpic: dh = 0, sweep P at constant enthalpy (throttling)
            Isentropic:  ds = 0, sweep P at constant entropy (real-fluid)
            Polytropic:  p·v^n = const enforced with real-fluid density
                         (not the ideal-gas T-P relation)

        Args:
            fluid: Fluid name
            process_type: One of the process types above
            initial_T: Initial temperature (K)
            initial_P: Initial pressure (Pa)
            final_value: Final T (K) for Isobaric/Isochoric, final P (Pa) otherwise
            num_points: Number of points along the path
            polytropic_n: Polytropic exponent (for polytropic only)

        Returns:
            Dictionary with arrays for each property along the path
            ('Phase' is an array of strings)

        Raises:
            ValueError: If the initial state or inputs are invalid
            NotImplementedError: For unsupported process types
        """
        if initial_T <= 0:
            raise ValueError(f"Initial temperature must be positive (got {initial_T} K)")
        if initial_P <= 0:
            raise ValueError(f"Initial pressure must be positive (got {initial_P} Pa)")
        if not np.isfinite(final_value):
            raise ValueError("Final value must be a finite number")

        n_q = max(5, num_points // 5)  # points inserted across the dome

        def initial_prop(key: str) -> float:
            try:
                return PropsSI(key, 'T', initial_T, 'P', initial_P, fluid)
            except Exception as e:
                raise ValueError(
                    f"Invalid initial state for {fluid} "
                    f"(T={initial_T:.2f} K, P={initial_P:.4g} Pa): {e}") from e

        pairs: list = []

        if process_type == 'Isobaric':
            if final_value <= 0:
                raise ValueError("Final temperature must be positive")
            T_points = np.linspace(initial_T, final_value, num_points)
            t_sat = None
            try:
                if initial_P < PropsSI('Pcrit', fluid):
                    t_sat = PropsSI('T', 'P', initial_P, 'Q', 0, fluid)
            except Exception:
                t_sat = None
            lo, hi = min(initial_T, final_value), max(initial_T, final_value)
            if t_sat is not None and lo < t_sat < hi:
                heating = final_value > initial_T
                before = [t for t in T_points
                          if (t < t_sat) == heating and abs(t - t_sat) > 1e-9]
                after = [t for t in T_points
                         if (t < t_sat) != heating and abs(t - t_sat) > 1e-9]
                q_lo, q_hi = (0.0, 1.0) if heating else (1.0, 0.0)
                pairs = ([('T', t, 'P', initial_P) for t in before]
                         + self._two_phase_pairs('P', initial_P, q_lo, q_hi, n_q)
                         + [('T', t, 'P', initial_P) for t in after])
            else:
                pairs = [('T', t, 'P', initial_P) for t in T_points]

        elif process_type == 'Isothermal':
            if final_value <= 0:
                raise ValueError("Final pressure must be positive")
            P_points = np.linspace(initial_P, final_value, num_points)
            p_sat = None
            try:
                if initial_T < PropsSI('Tcrit', fluid):
                    p_sat = PropsSI('P', 'T', initial_T, 'Q', 0, fluid)
            except Exception:
                p_sat = None
            lo, hi = min(initial_P, final_value), max(initial_P, final_value)
            if p_sat is not None and lo < p_sat < hi:
                compressing = final_value > initial_P
                before = [p for p in P_points
                          if (p < p_sat) == compressing and abs(p - p_sat) > 1e-9 * p_sat]
                after = [p for p in P_points
                         if (p < p_sat) != compressing and abs(p - p_sat) > 1e-9 * p_sat]
                # Compression crosses vapor -> liquid (Q: 1 -> 0)
                q_lo, q_hi = (1.0, 0.0) if compressing else (0.0, 1.0)
                pairs = ([('T', initial_T, 'P', p) for p in before]
                         + self._two_phase_pairs('T', initial_T, q_lo, q_hi, n_q)
                         + [('T', initial_T, 'P', p) for p in after])
            else:
                pairs = [('T', initial_T, 'P', p) for p in P_points]

        elif process_type == 'Isochoric':
            if final_value <= 0:
                raise ValueError("Final temperature must be positive")
            D0 = initial_prop('D')
            T_points = np.linspace(initial_T, final_value, num_points)
            pairs = [('T', t, 'D', D0) for t in T_points]

        elif process_type == 'Isenthalpic':
            if final_value <= 0:
                raise ValueError("Final pressure must be positive")
            H0 = initial_prop('H')
            P_points = np.linspace(initial_P, final_value, num_points)
            pairs = [('P', p, 'H', H0) for p in P_points]

        elif process_type == 'Isentropic':
            if final_value <= 0:
                raise ValueError("Final pressure must be positive")
            S0 = initial_prop('S')
            P_points = np.linspace(initial_P, final_value, num_points)
            pairs = [('P', p, 'S', S0) for p in P_points]

        elif process_type == 'Polytropic':
            if final_value <= 0:
                raise ValueError("Final pressure must be positive")
            if polytropic_n <= 0:
                raise ValueError(f"Polytropic exponent must be positive (got {polytropic_n})")
            # Enforce p·v^n = const with real-fluid density:
            # rho(P) = rho0 · (P/P0)^(1/n)
            D0 = initial_prop('D')
            P_points = np.linspace(initial_P, final_value, num_points)
            pairs = [('P', p, 'D', D0 * (p / initial_P) ** (1.0 / polytropic_n))
                     for p in P_points]

        else:
            raise NotImplementedError(f"Process type '{process_type}' not implemented.")

        rows = [self._path_state(fluid, n1, v1, n2, v2) for n1, v1, n2, v2 in pairs]

        results = {key: np.array([row[key] for row in rows])
                   for key in self._PATH_KEYS}
        results['Phase'] = np.array([row['Phase'] for row in rows])
        return results
