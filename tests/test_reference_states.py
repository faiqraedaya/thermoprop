"""
Reference-state tests for the property core.

Reference values are from the NIST Webbook (IAPWS-95 for water); tolerances
are set to catch unit/phase/formula errors, not last-digit EOS differences.
"""

import math

import pytest

from thermoprop.core.mixture_calculator import MixtureCalculator
from thermoprop.core.mixture_component import MixtureComponent


@pytest.fixture(scope='module')
def calc():
    return MixtureCalculator()


@pytest.fixture(scope='module')
def sat(calc):
    """Water saturation at 1 atm."""
    return calc.calculate_saturation_properties('Water', 'P', 1.01325, 'bar')


@pytest.fixture(scope='module')
def props(calc):
    """Liquid water at 25 °C / 1 atm."""
    return calc.calculate_single_point_properties(
        'Water', 'T', 25, '°C', 'P', 1.01325, 'bara')


class TestWaterSaturation:
    """Water saturation at 1 atm: NIST Webbook values."""

    def test_saturation_temperature(self, sat):
        assert sat['Saturation Temperature'][0] == pytest.approx(373.124, abs=0.05)

    def test_liquid_density(self, sat):
        assert sat['Liquid Density'][0] == pytest.approx(958.37, rel=1e-3)

    def test_vapor_density(self, sat):
        assert sat['Vapor Density'][0] == pytest.approx(0.5976, rel=1e-3)

    def test_latent_heat(self, sat):
        assert sat['Latent Heat'][0] == pytest.approx(2256.5e3, rel=1e-3)

    def test_branches_consistent(self, sat):
        # vapor enthalpy/entropy above liquid (no swapped roots)
        assert sat['Vapor Enthalpy'][0] > sat['Liquid Enthalpy'][0]
        assert sat['Vapor Entropy'][0] > sat['Liquid Entropy'][0]
        assert sat['Liquid Density'][0] > sat['Vapor Density'][0]

    def test_above_critical_rejected(self, calc):
        with pytest.raises(ValueError, match='critical'):
            calc.calculate_saturation_properties('Water', 'T', 700, 'K')
        with pytest.raises(ValueError, match='critical'):
            calc.calculate_saturation_properties('Water', 'P', 30, 'MPa')

    def test_pseudo_pure_reports_bubble_and_dew(self, calc):
        res = calc.calculate_saturation_properties('Air', 'P', 1.0, 'bar')
        assert 'Saturation Temperature (bubble)' in res
        assert 'Saturation Temperature (dew)' in res
        assert (res['Saturation Temperature (dew)'][0]
                > res['Saturation Temperature (bubble)'][0])


class TestSinglePoint:
    """Liquid water at 25 °C / 1 atm: NIST Webbook values."""

    def test_density(self, props):
        assert props['Density'][0] == pytest.approx(997.05, rel=1e-3)

    def test_cp(self, props):
        assert props['Isobaric Heat Capacity'][0] == pytest.approx(4181.3, rel=1e-3)

    def test_viscosity(self, props):
        assert props['Viscosity'][0] == pytest.approx(8.90e-4, rel=5e-3)

    def test_speed_of_sound(self, props):
        assert props['Speed of Sound'][0] == pytest.approx(1496.7, rel=1e-3)

    def test_phase_is_string(self, props):
        assert props['Phase'][0] == 'liquid'

    def test_quality_is_nan_outside_dome(self, props):
        # CoolProp reports Q = -1 for single-phase; must be shown as N/A
        assert math.isnan(props['Quality'][0])

    def test_unsupported_pair_rejected(self, calc):
        with pytest.raises(ValueError, match='not supported'):
            calc.calculate_single_point_properties(
                'Water', 'T', 25, '°C', 'H', 100, 'kJ/kg')

    def test_same_property_twice_rejected(self, calc):
        with pytest.raises(ValueError):
            calc.calculate_single_point_properties(
                'Water', 'T', 25, '°C', 'T', 300, 'K')


class TestUnitConversion:
    def test_temperature(self, calc):
        assert calc._convert_to_si(25, '°C', 'T') == pytest.approx(298.15)
        assert calc._convert_to_si(212, '°F', 'T') == pytest.approx(373.15)

    def test_pressure(self, calc):
        assert calc._convert_to_si(1, 'atm', 'P') == pytest.approx(101325)
        assert calc._convert_to_si(0, 'barg', 'P') == pytest.approx(1.01325e5)
        assert calc._convert_to_si(0, 'psig', 'P') == pytest.approx(101325, rel=1e-4)

    def test_unphysical_rejected(self, calc):
        with pytest.raises(ValueError):
            calc._convert_to_si(-300, '°C', 'T')
        with pytest.raises(ValueError):
            calc._convert_to_si(-5, 'bar', 'P')

    def test_unknown_unit_rejected(self, calc):
        with pytest.raises(ValueError):
            calc._convert_to_si(1, 'furlongs', 'P')


class TestMixtureComponent:
    def test_molecular_weight(self):
        comp = MixtureComponent('Water', 1.0)
        assert comp.molecular_weight == pytest.approx(18.015, rel=1e-3)

    def test_unknown_fluid_raises(self):
        with pytest.raises(ValueError, match='NotAFluid'):
            MixtureComponent('NotAFluid', 0.5)
