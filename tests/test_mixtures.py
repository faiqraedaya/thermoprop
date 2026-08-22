"""
Mixture-model tests: ideal-gas (Gibbs-Dalton) and humid-air.
"""

import numpy as np
import pytest
from CoolProp.CoolProp import PropsSI
from CoolProp.HumidAirProp import HAPropsSI

from thermoprop.core.mixture_calculator import MixtureCalculator
from thermoprop.core.mixture_component import MixtureComponent


@pytest.fixture(scope='module')
def calc():
    return MixtureCalculator()


def make(components):
    return [MixtureComponent(name, x) for name, x in components]


class TestIdealGasMixture:
    def test_air_preset_against_real_air(self, calc):
        """Ideal mixing of the air preset must match CoolProp real air at STP."""
        comps = make(calc.predefined_mixtures['Air'])
        res, err = calc.calculate_mixture_properties(comps, 298.15, 101325, 'Ideal Gas')
        assert err is None
        assert res['Density'][0] == pytest.approx(1.184, rel=2e-3)
        assert res['Isobaric Heat Capacity'][0] == pytest.approx(1006.3, rel=5e-3)
        assert res['Speed of Sound'][0] == pytest.approx(346.3, rel=5e-3)
        # Wilke viscosity vs real air correlation
        mu_air = PropsSI('V', 'T', 298.15, 'P', 101325, 'Air')
        assert res['Viscosity'][0] == pytest.approx(mu_air, rel=0.02)

    def test_single_component_reduces_to_pure_fluid(self, calc):
        """x=1 nitrogen must reproduce the pure-fluid CoolProp state exactly."""
        comps = make([('Nitrogen', 1.0)])
        res, err = calc.calculate_mixture_properties(comps, 300.0, 101325, 'Ideal Gas')
        assert err is None
        for key, cp_key in [('Enthalpy', 'H'), ('Entropy', 'S'),
                            ('Isobaric Heat Capacity', 'Cpmass'),
                            ('Viscosity', 'V'), ('Thermal Conductivity', 'L')]:
            ref = PropsSI(cp_key, 'T', 300.0, 'P', 101325, 'Nitrogen')
            assert res[key][0] == pytest.approx(ref, rel=1e-9), key

    def test_entropy_includes_mixing_term(self, calc):
        """
        Equimolar N2/O2 entropy must exceed the mole-weighted average of the
        pure-component entropies at full pressure by the ideal entropy of
        mixing, -R Σ x ln x (mass basis).
        """
        T, P = 300.0, 101325.0
        comps = make([('Nitrogen', 0.5), ('Oxygen', 0.5)])
        res, err = calc.calculate_mixture_properties(comps, T, P, 'Ideal Gas')
        assert err is None

        M_n2 = PropsSI('M', 'Nitrogen')
        M_o2 = PropsSI('M', 'Oxygen')
        M_mix = 0.5 * M_n2 + 0.5 * M_o2
        w_n2 = 0.5 * M_n2 / M_mix
        w_o2 = 0.5 * M_o2 / M_mix
        s_full = (w_n2 * PropsSI('S', 'T', T, 'P', P, 'Nitrogen')
                  + w_o2 * PropsSI('S', 'T', T, 'P', P, 'Oxygen'))
        R_mass = 8.314462618 / M_mix  # J/kg/K
        s_mixing = -R_mass * (0.5 * np.log(0.5) + 0.5 * np.log(0.5))
        assert res['Entropy'][0] - s_full == pytest.approx(s_mixing, rel=0.02)

    def test_condensable_below_dew_point_rejected(self, calc):
        """Flue gas with 8% H2O at 25 °C is below its dew point -> clear error."""
        comps = make(calc.predefined_mixtures['Flue Gas (Coal)'])
        res, err = calc.calculate_mixture_properties(comps, 298.15, 101325, 'Ideal Gas')
        assert res is None
        assert 'dew point' in err

    def test_flue_gas_above_dew_point(self, calc):
        """Same flue gas at 60 °C is fully gaseous; Cp must be gas-phase (~1080)."""
        comps = make(calc.predefined_mixtures['Flue Gas (Coal)'])
        res, err = calc.calculate_mixture_properties(comps, 333.15, 101325, 'Ideal Gas')
        assert err is None
        # liquid-water pollution would push this to ~1150+
        assert 950 < res['Isobaric Heat Capacity'][0] < 1120

    def test_zero_composition_rejected(self, calc):
        comps = make([('Nitrogen', 0.0)])
        res, err = calc.calculate_mixture_properties(comps, 300, 101325, 'Ideal Gas')
        assert res is None and err

    def test_unphysical_state_rejected(self, calc):
        comps = make([('Nitrogen', 1.0)])
        res, err = calc.calculate_mixture_properties(comps, -10, 101325, 'Ideal Gas')
        assert res is None and 'absolute zero' in err


class TestHumidAir:
    def test_basis_consistency(self, calc):
        """Enthalpy/entropy must be per kg humid air ('Hha'/'Sha'), matching
        the density basis (1/'Vha')."""
        T, P = 303.15, 101325.0
        comps = make([('Water', 0.02), ('Nitrogen', 0.78), ('Oxygen', 0.20)])
        res, err = calc.calculate_mixture_properties(comps, T, P, 'Humid Air')
        assert err is None

        RH = res['Relative Humidity'][0] / 100
        assert res['Enthalpy'][0] == pytest.approx(
            HAPropsSI('Hha', 'T', T, 'P', P, 'R', RH), rel=1e-9)
        assert res['Entropy'][0] == pytest.approx(
            HAPropsSI('Sha', 'T', T, 'P', P, 'R', RH), rel=1e-9)
        assert res['Density'][0] == pytest.approx(
            1.0 / HAPropsSI('Vha', 'T', T, 'P', P, 'R', RH), rel=1e-9)

    def test_no_silent_fallback(self, calc):
        """Out-of-range humid-air states must error, not silently switch model."""
        comps = make([('Water', 0.02), ('Nitrogen', 0.78), ('Oxygen', 0.20)])
        res, err = calc.calculate_mixture_properties(comps, 150.0, 101325, 'Humid Air')
        assert res is None
        assert err is not None

    def test_non_air_component_rejected(self, calc):
        comps = make([('Water', 0.02), ('Methane', 0.98)])
        res, err = calc.calculate_mixture_properties(comps, 303.15, 101325, 'Humid Air')
        assert res is None
        assert 'Methane' in err

    def test_supersaturated_rejected(self, calc):
        """30% water at 25 °C, 1 atm is far above saturation -> error."""
        comps = make([('Water', 0.30), ('Nitrogen', 0.55), ('Oxygen', 0.15)])
        res, err = calc.calculate_mixture_properties(comps, 298.15, 101325, 'Humid Air')
        assert res is None
        assert 'supersaturated' in err
