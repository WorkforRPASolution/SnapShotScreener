# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building snapshot-screener as a single executable."""

a = Analysis(
    ['snapshot_screener/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('snapshot_screener/report/templates/*.j2', 'snapshot_screener/report/templates'),
    ],
    hiddenimports=[
        'cassandra.io.asyncorereactor',
        'cassandra.io.asyncioreactor',
        'cassandra.policies',
        'cassandra.auth',
        'cassandra.cqltypes',
        'cassandra.pool',
        'cassandra.cluster',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter',
        'matplotlib.backends',
        'IPython',
        'notebook',
        'sphinx',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='snapshot-screener',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
