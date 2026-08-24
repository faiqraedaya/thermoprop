# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for ThermoProp.

Optimized for minimum on-disk size while still using a directory bundle
(no --onefile). Trims unused PySide6 modules, alternative matplotlib
backends, and other heavy libs the app does not import.
"""

from PyInstaller.utils.hooks import collect_submodules


block_cipher = None


# --- Heavy modules / sub-packages we never import -----------------------------
EXCLUDES = [
    # GUI toolkits we don't use
    'tkinter',
    'PyQt5',
    'PyQt6',
    'PySide2',

    # Test / dev tooling
    # NOTE: do NOT exclude 'unittest' — matplotlib/pyparsing import it at load.
    'pydoc',
    'pytest',
    'IPython',
    'jupyter',
    'notebook',
    'sphinx',

    # Matplotlib backends we don't use (we only use QtAgg)
    'matplotlib.tests',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_tkcairo',
    'matplotlib.backends.backend_wx',
    'matplotlib.backends.backend_wxagg',
    'matplotlib.backends.backend_wxcairo',
    'matplotlib.backends.backend_gtk3agg',
    'matplotlib.backends.backend_gtk3cairo',
    'matplotlib.backends.backend_gtk4agg',
    'matplotlib.backends.backend_gtk4cairo',
    'matplotlib.backends.backend_webagg',
    'matplotlib.backends.backend_nbagg',
    'matplotlib.backends.backend_macosx',

    # Numpy / pandas extras
    'numpy.tests',
    'numpy.f2py',
    'pandas.tests',

    # PySide6 sub-modules we do not import
    'PySide6.Qt3DAnimation',
    'PySide6.Qt3DCore',
    'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic',
    'PySide6.Qt3DRender',
    'PySide6.QtBluetooth',
    'PySide6.QtCharts',
    'PySide6.QtConcurrent',
    'PySide6.QtDataVisualization',
    'PySide6.QtDBus',
    'PySide6.QtDesigner',
    'PySide6.QtGraphs',
    'PySide6.QtGraphsWidgets',
    'PySide6.QtHelp',
    'PySide6.QtHttpServer',
    'PySide6.QtLocation',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtNetworkAuth',
    'PySide6.QtNfc',
    'PySide6.QtOpenGL',
    'PySide6.QtOpenGLWidgets',
    'PySide6.QtPdf',
    'PySide6.QtPdfWidgets',
    'PySide6.QtPositioning',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuick3D',
    'PySide6.QtQuickControls2',
    'PySide6.QtQuickWidgets',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    'PySide6.QtSensors',
    'PySide6.QtSerialBus',
    'PySide6.QtSerialPort',
    'PySide6.QtSpatialAudio',
    'PySide6.QtSql',
    'PySide6.QtStateMachine',
    'PySide6.QtSvgWidgets',
    'PySide6.QtTest',
    'PySide6.QtTextToSpeech',
    'PySide6.QtUiTools',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineQuick',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtXml',
    'PySide6.QtAsyncio',
    'PySide6.scripts',
]


# Hidden imports CoolProp / matplotlib sometimes need at runtime.
HIDDEN = [
    'CoolProp.CoolProp',
    'CoolProp.HumidAirProp',
    'PySide6.QtSvg',          # the icon set is rendered from SVG at runtime
]
HIDDEN += collect_submodules('pint')


a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=[],
    datas=[('src/thermoprop/gui/fonts', 'thermoprop/gui/fonts')],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ThermoProp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[
        # UPX corrupts some Qt/Python DLLs; keep these untouched.
        'vcruntime140.dll',
        'python313.dll',
        'Qt6Core.dll',
        'Qt6Gui.dll',
        'Qt6Widgets.dll',
        'Qt6Network.dll',
        'Qt6Svg.dll',
        'Qt6Pdf.dll',
        'qwindows.dll',
    ],
    name='ThermoProp',
)
