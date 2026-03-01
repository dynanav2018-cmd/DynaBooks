# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for DynaBooks standalone app."""

import importlib
import os
import pathlib
import tempfile

# Build outside Dropbox to avoid file lock conflicts
_build_dir = os.path.join(tempfile.gettempdir(), 'dynabooks_build')
_dist_dir = os.path.join(tempfile.gettempdir(), 'dynabooks_dist')

block_cipher = None

# Find python-accounting's config.toml (sits in site-packages root)
_pa_pkg = pathlib.Path(importlib.import_module('python_accounting.config').__file__).parent
_config_toml = str(_pa_pkg.parent / 'config.toml')

a = Analysis(
    ['dynabooks_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('frontend/dist', 'frontend/dist'),
        ('backend/templates', 'backend/templates'),
        (_config_toml, '.'),
    ],
    hiddenimports=[
        'python_accounting',
        'python_accounting.config',
        'python_accounting.database',
        'python_accounting.database.engine',
        'python_accounting.database.session',
        'python_accounting.database.accounting_functions',
        'python_accounting.models',
        'python_accounting.transactions',
        'python_accounting.reports',
        'python_accounting.exceptions',
        'python_accounting.mixins',
        'python_accounting.utils',
        'sqlalchemy.dialects.sqlite',
        'strenum',
        'xhtml2pdf',
        'xhtml2pdf.pisa',
        'html5lib',
        'reportlab',
        'dateutil',
        'dateutil.relativedelta',
        'pystray',
        'PIL',
        'reportlab.graphics.barcode.code128',
        'reportlab.graphics.barcode.code39',
        'reportlab.graphics.barcode.code93',
        'reportlab.graphics.barcode.usps',
        'reportlab.graphics.barcode.usps4s',
        'reportlab.graphics.barcode.ecc200datamatrix',
        'reportlab.graphics.barcode.eanbc',
        'reportlab.graphics.barcode.fourstate',
        'reportlab.graphics.barcode.lto',
        'reportlab.graphics.barcode.qr',
        'reportlab.graphics.barcode.qrencoder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DynaBooks',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DynaBooks',
)

# ── Post-build: copy install.bat and dist_data alongside the EXE ──
import shutil

_dist_app = os.path.join(DISTPATH, 'DynaBooks')

# install.bat
_install_bat = os.path.join(SPECPATH, 'install.bat')
if os.path.isfile(_install_bat):
    shutil.copy2(_install_bat, _dist_app)

# dist_data/ (clean default company database)
_dist_data_src = os.path.join(SPECPATH, 'dist_data')
_dist_data_dst = os.path.join(_dist_app, 'dist_data')
if os.path.isdir(_dist_data_src):
    if os.path.isdir(_dist_data_dst):
        shutil.rmtree(_dist_data_dst)
    shutil.copytree(_dist_data_src, _dist_data_dst)
