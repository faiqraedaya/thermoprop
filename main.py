"""
THERMOPROP
Thermophysical Properties Calculator

Version: 2.6.0
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
- 2.5.0 - 2026-08-24
    - User-interface overhaul against the shared PySide6 design system:
      ui/theme.py is now the sole styling authority (one stylesheet, one
      token set, verified contrast ladder), ui/layout.py puts every layout
      on the 8 px grid, calculations run off the GUI thread behind a shared
      busy state, every table and plot has an empty state, validation and
      calculation errors report inline instead of in a modal, matplotlib
      chrome is neutral with a validated categorical series palette, and
      the per-component comparison table on the Mixture tab is populated
      rather than permanently blank
- 2.6.0 - 2026-08-24
    - Vertical navigation sidebar (resizable, hideable with Ctrl+B) with a
      hand-authored 16 px Lucide-geometry icon set, replacing the horizontal
      tab bar; each page names itself in a title at the top; Inter now ships
      with the app in gui/fonts instead of being assumed present on the
      host; modules reorganised into src/thermoprop/core (calculation) and
      src/thermoprop/gui (interface), and the unused table_utils module was
      removed
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from thermoprop.app import main

if __name__ == '__main__':
    main()
