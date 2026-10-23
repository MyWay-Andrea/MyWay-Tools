import os
import sys
from pathlib import Path

spec_dir = Path(SPEC).resolve().parent
if str(spec_dir) not in sys.path:
    sys.path.insert(0, str(spec_dir))

from build_guard import build_script_datas, print_inventory

runtime_path = r'C:\TEMP\_runtime'
site_packages = os.path.join(runtime_path, 'Lib', 'site-packages')

block_cipher = None

# Il controllo elenca le risorse selezionate e gli eventuali file locali
# esclusi. build_script_datas aggiunge i file singolarmente, quindi PyInstaller
# non puo' ricopiare ricorsivamente .env, credenziali o cache.
scripts_root = spec_dir / 'scripts'
print_inventory(scripts_root)
script_datas = build_script_datas(scripts_root)

a = Analysis(
    ['menu.py'],
    pathex=[
        os.path.dirname(os.path.abspath(SPEC)),
        runtime_path,
        site_packages,
    ],
    binaries=[],
    datas=[
        ('version.txt', '.'),
        ('logo.ico', '.'),
    ] + script_datas,
    hiddenimports=[
    'xlwings',
    'xlrd',
    'openpyxl',
    'pandas',
    'win32com',
    'win32com.client',
    'pythoncom',
    'pywintypes',
    'PySide6',
    'PySide6.QtWidgets',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'pyarrow',
],
    hookspath=[],
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
    name='MyWayTools',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='logo.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MyWayTools',
)
