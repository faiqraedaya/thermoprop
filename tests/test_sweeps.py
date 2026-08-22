"""
Diagram-sweep tests: fluid-specific temperature ranges (no hardcoded
water triple point) and internally consistent saturation branches.
"""

import numpy as np
import pytest
from CoolProp.CoolProp import PropsSI

from thermoprop.core.sweeps import saturation_sweep, temperature_bounds


class TestTemperatureBounds:
    def test_water(self):
        tt, tc = temperature_bounds('Water')
        assert tt == pytest.approx(273.16, abs=0.01)
        assert tc == pytest.approx(647.096, abs=0.01)

    def test_cryogen(self):
        """Nitrogen bounds must be its own triple point, not 273.16 K."""
        tt, tc = temperature_bounds('Nitrogen')
        assert tt == pytest.approx(63.151, abs=0.1)
        assert tc == pytest.approx(126.192, abs=0.1)


class TestSaturationSweep:
    @pytest.mark.parametrize('fluid', ['Water', 'Nitrogen', 'CO2', 'Benzene'])
    def test_mostly_valid_points(self, fluid):
        """The sweep must produce valid data across the whole dome for
        cryogens and high-triple-point fluids alike."""
        sat = saturation_sweep(fluid, 50)
        valid = np.isfinite(sat['P'])
        assert valid.mean() > 0.9, f"{fluid}: only {valid.sum()}/50 valid points"

    def test_branch_consistency(self):
        sat = saturation_sweep('Water', 50)
        v = np.isfinite(sat['P'])
        assert np.all(sat['rho_liq'][v] > sat['rho_vap'][v])
        assert np.all(sat['h_vap'][v] > sat['h_liq'][v])
        assert np.all(sat['s_vap'][v] > sat['s_liq'][v])
        # monotonic vapor-pressure curve
        assert np.all(np.diff(sat['P'][v]) > 0)

    def test_no_extrapolation_past_critical(self):
        sat = saturation_sweep('Water', 50)
        assert sat['T'].max() < PropsSI('Tcrit', 'Water')

    def test_windowed_sweep(self):
        sat = saturation_sweep('Water', 20, t_min=350, t_max=400)
        assert sat['T'].min() >= 350 - 1e-9
        assert sat['T'].max() <= 400 + 1e-9
