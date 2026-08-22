"""
Shared property-sweep routines for ThermoProp.

These keep thermodynamic sweeps out of the plotting/UI layer: the canvas and
tabs consume the SI arrays returned here and only draw them. Failed points
are returned as NaN so partial curves still plot.
"""

import logging
from typing import Optional

import numpy as np
from CoolProp.CoolProp import PropsSI

logger = logging.getLogger(__name__)


def temperature_bounds(fluid: str) -> tuple:
    """
    Saturation temperature bounds (T_min, T_crit) for a fluid, in K.

    T_min is the triple-point temperature where available, otherwise the
    fluid's minimum temperature limit (never a hardcoded water value).
    """
    Tc = PropsSI('Tcrit', fluid)
    for key in ('Ttriple', 'Tmin'):
        try:
            return PropsSI(key, fluid), Tc
        except Exception:
            continue
    logger.warning("No triple-point or Tmin available for %s; using 0.3·Tc", fluid)
    return 0.3 * Tc, Tc


def saturation_sweep(fluid: str, n: int = 100,
                     t_min: Optional[float] = None,
                     t_max: Optional[float] = None) -> dict:
    """
    Sweep the saturation curve of a pure (or pseudo-pure) fluid.

    Args:
        fluid: Fluid name
        n: Number of points
        t_min, t_max: Optional temperature window (K); clipped to the fluid's
            valid saturation range [T_triple, 0.999·T_crit]

    Returns:
        Dict of SI numpy arrays: 'T' (K), 'P' (Pa, bubble), 'rho_liq',
        'rho_vap' (kg/m³), 'h_liq', 'h_vap' (J/kg), 's_liq', 's_vap' (J/kg/K).
        Failed points are NaN.
    """
    Tt, Tc = temperature_bounds(fluid)
    lo = max(Tt, t_min) if t_min is not None else Tt
    hi = min(0.999 * Tc, t_max) if t_max is not None else 0.999 * Tc
    T = np.linspace(lo, hi, n)

    out = {key: np.full(n, np.nan) for key in
           ('P', 'rho_liq', 'rho_vap', 'h_liq', 'h_vap', 's_liq', 's_vap')}
    out['T'] = T

    for i, t in enumerate(T):
        try:
            out['P'][i] = PropsSI('P', 'T', t, 'Q', 0, fluid)
            out['rho_liq'][i] = PropsSI('D', 'T', t, 'Q', 0, fluid)
            out['rho_vap'][i] = PropsSI('D', 'T', t, 'Q', 1, fluid)
            out['h_liq'][i] = PropsSI('H', 'T', t, 'Q', 0, fluid)
            out['h_vap'][i] = PropsSI('H', 'T', t, 'Q', 1, fluid)
            out['s_liq'][i] = PropsSI('S', 'T', t, 'Q', 0, fluid)
            out['s_vap'][i] = PropsSI('S', 'T', t, 'Q', 1, fluid)
        except Exception:
            continue  # leave NaN

    return out


def isobar_sweep(fluid: str, pressure: float, n: int = 50,
                 t_min: Optional[float] = None,
                 t_max: Optional[float] = None) -> dict:
    """
    Sweep T at constant pressure, returning h and s (SI). Failed points NaN.
    Default range: T_triple to 1.2·T_crit.
    """
    Tt, Tc = temperature_bounds(fluid)
    lo = t_min if t_min is not None else Tt
    hi = t_max if t_max is not None else 1.2 * Tc
    T = np.linspace(lo, hi, n)
    h = np.full(n, np.nan)
    s = np.full(n, np.nan)
    for i, t in enumerate(T):
        try:
            h[i] = PropsSI('H', 'T', t, 'P', pressure, fluid)
            s[i] = PropsSI('S', 'T', t, 'P', pressure, fluid)
        except Exception:
            continue
    return {'T': T, 'h': h, 's': s}
