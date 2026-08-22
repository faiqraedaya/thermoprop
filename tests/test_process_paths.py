"""
Process-path tests: each path type is checked against its defining
constraint (dP=0, dv=0, dT=0, dh=0, ds=0, p·v^n=const).
"""

import numpy as np
import pytest
from CoolProp.CoolProp import PropsSI

from thermoprop.core.mixture_calculator import MixtureCalculator


@pytest.fixture(scope='module')
def calc():
    return MixtureCalculator()


def finite(arr):
    return arr[np.isfinite(arr)]


class TestDefiningConstraints:
    def test_isobaric_dp_zero(self, calc):
        r = calc.simulate_process_path('Nitrogen', 'Isobaric', 300, 5e5, 400, 20)
        assert np.allclose(finite(r['Pressure']), 5e5, rtol=1e-9)

    def test_isochoric_dv_zero(self, calc):
        r = calc.simulate_process_path('Nitrogen', 'Isochoric', 300, 5e5, 500, 20)
        assert np.allclose(finite(r['Density']), r['Density'][0], rtol=1e-9)

    def test_isothermal_dt_zero(self, calc):
        r = calc.simulate_process_path('Nitrogen', 'Isothermal', 300, 1e5, 50e5, 20)
        assert np.allclose(finite(r['Temperature']), 300.0, rtol=1e-9)

    def test_isenthalpic_dh_zero_and_jt_cooling(self, calc):
        """Steam 10 bar / 250 °C throttled to 1 bar: h constant, T drops."""
        r = calc.simulate_process_path('Water', 'Isenthalpic', 523.15, 10e5, 1e5, 20)
        assert np.allclose(finite(r['Enthalpy']), r['Enthalpy'][0], rtol=1e-9)
        assert r['Temperature'][-1] < r['Temperature'][0]  # real-gas JT cooling

    def test_isentropic_ds_zero(self, calc):
        r = calc.simulate_process_path('Air', 'Isentropic', 300, 1e5, 10e5, 20)
        assert np.allclose(finite(r['Entropy']), r['Entropy'][0], rtol=1e-9)

    def test_polytropic_pvn_constant_real_gas(self, calc):
        """p·v^n must be constant along the path even for strongly non-ideal
        CO2 near the critical point (the ideal-gas T-P shortcut drifts +52%)."""
        n = 1.3
        r = calc.simulate_process_path('CO2', 'Polytropic', 310.0, 80e5, 160e5,
                                       20, polytropic_n=n)
        pv_n = r['Pressure'] * (1.0 / r['Density']) ** n
        pv_n = finite(pv_n)
        assert pv_n.max() / pv_n.min() == pytest.approx(1.0, rel=1e-6)

    def test_polytropic_matches_ideal_relation_for_near_ideal_gas(self, calc):
        """For near-ideal air the pv^n path must agree with the classical
        T-P relation to within ~1 K."""
        n = 1.3
        r = calc.simulate_process_path('Air', 'Polytropic', 300.0, 1e5, 10e5,
                                       20, polytropic_n=n)
        T_ideal = 300.0 * (10.0) ** ((n - 1) / n)
        assert r['Temperature'][-1] == pytest.approx(T_ideal, abs=2.0)


class TestTwoPhaseHandling:
    def test_isobaric_boiling_plateau(self, calc):
        """Water heated 25→150 °C at 1 atm must include a two-phase segment
        with quality spanning 0..1 at T_sat."""
        r = calc.simulate_process_path('Water', 'Isobaric', 298.15, 101325, 423.15, 50)
        q = r['Quality'][np.isfinite(r['Quality'])]
        assert q.size >= 5
        assert q.min() == pytest.approx(0.0, abs=1e-9)
        assert q.max() == pytest.approx(1.0, abs=1e-9)
        # two-phase points sit at the saturation temperature
        t_sat = PropsSI('T', 'P', 101325, 'Q', 0, 'Water')
        two_phase = r['Phase'] == 'twophase'
        assert np.allclose(r['Temperature'][two_phase], t_sat, atol=0.01)
        # enthalpy is monotonically increasing through the plateau
        h = finite(r['Enthalpy'])
        assert np.all(np.diff(h) > -1e-6)

    def test_isothermal_condensation_segment(self, calc):
        """Steam compressed isothermally at 150 °C through P_sat must show a
        vapor->liquid two-phase segment (Q from 1 to 0)."""
        r = calc.simulate_process_path('Water', 'Isothermal', 423.15, 1e5, 10e5, 50)
        q = r['Quality'][np.isfinite(r['Quality'])]
        assert q.size >= 5
        assert q[0] == pytest.approx(1.0, abs=1e-9)
        assert q[-1] == pytest.approx(0.0, abs=1e-9)

    def test_quality_nan_outside_dome(self, calc):
        """Single-phase points must report NaN quality, not CoolProp's -1."""
        r = calc.simulate_process_path('Nitrogen', 'Isobaric', 300, 1e5, 400, 10)
        assert np.all(np.isnan(r['Quality']))

    def test_phase_is_string(self, calc):
        r = calc.simulate_process_path('Nitrogen', 'Isobaric', 300, 1e5, 400, 10)
        assert all(isinstance(p, str) for p in r['Phase'])
        assert 'gas' in r['Phase'][0] or r['Phase'][0] == 'supercritical_gas'


class TestValidation:
    def test_invalid_initial_state(self, calc):
        with pytest.raises(ValueError, match='Initial'):
            calc.simulate_process_path('Water', 'Isenthalpic', -5, 1e5, 2e5, 10)

    def test_unknown_process(self, calc):
        with pytest.raises(NotImplementedError):
            calc.simulate_process_path('Water', 'Sideways', 300, 1e5, 2e5, 10)

    def test_nonpositive_final_pressure(self, calc):
        with pytest.raises(ValueError):
            calc.simulate_process_path('Water', 'Isothermal', 300, 1e5, -2e5, 10)
