import os
import sys

# Allow running the tests from a source checkout without installing the package
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)
