"""
THERMOPROP
Thermophysical Properties Calculator

Version: 2.4.0
Author: Faiq Raedaya

Launcher for running from a source checkout (``python main.py``).
The application itself lives in the ``thermoprop`` package under ``src/``;
see src/thermoprop/app.py.

Changelog:
- 1.0.0 - 2025-05-03
    - Initial build with basic functionality
- 2.0.0 - 2025-05-28
    - Full rewrite with improved functionality and user interface
- 2.1.0 - 2025-05-29
    - Separated helper classes into individual files
- 2.2.0 - 2025-06-23
    - Fixed UI not running backend calculations
- 2.3.0 - 2026-05-20
    - Migrated to PySide6
    - Removed custom style
    - Removed quick calc dialog and help/about
- 2.4.0 - 2026-07-08
    - Correctness overhaul after codebase audit: Gibbs-Dalton ideal-gas
      mixing at partial pressures with dew-point guard, Wilke/Mason-Saxena
      transport mixing, consistent humid-air basis (Hha/Sha), real-fluid
      polytropic paths (p·v^n = const), two-phase segments on isobaric and
      isothermal paths, fluid-specific diagram temperature ranges,
      corrected phase-envelope regions, working unit converter for offset
      units, working export/project persistence, and a pytest suite with
      reference-state checks
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from thermoprop.app import main

if __name__ == '__main__':
    main()
