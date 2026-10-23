import os
import runpy

runtime_path = r'C:\TEMP\_runtime'
site_packages = os.path.join(runtime_path, 'Lib', 'site-packages')

block_cipher = None

# Includi soltanto i progetti richiamati da menu.py e le relative dipendenze
# condivise. In questo modo file locali come scripts/.env, cache e vecchi
# progetti non possono finire accidentalmente nell'installer.
script_datas = [
    ('scripts/config_env.py', 'scripts'),
    ('scripts/graph_sharepoint.py', 'scripts'),
    ('scripts/BUSINESS/common', 'scripts/BUSINESS/common'),
    ('scripts/BUSINESS/config', 'scripts/BUSINESS/config'),
    ('scripts/BUSINESS/02_(OLD)_APPUNTAMENTI_SETTIMANA', 'scripts/BUSINESS/02_(OLD)_APPUNTAMENTI_SETTIMANA'),
    ('scripts/BUSINESS/09_ESTRAZIONE_ORDINI_API', 'scripts/BUSINESS/09_ESTRAZIONE_ORDINI_API'),
    ('scripts/BUSINESS/10_ESTRAZIONE_OPP_API', 'scripts/BUSINESS/10_ESTRAZIONE_OPP_API'),
    ('scripts/BUSINESS/11_ESTRAZIONE_APP_API', 'scripts/BUSINESS/11_ESTRAZIONE_APP_API'),
    ('scripts/BUSINESS/12_FCST_BUSINESS', 'scripts/BUSINESS/12_FCST_BUSINESS'),
    ('scripts/BUSINESS/13_ESTRAI_FILE_GARA', 'scripts/BUSINESS/13_ESTRAI_FILE_GARA'),
    ('scripts/BUSINESS/14_ELABORA_CB', 'scripts/BUSINESS/14_ELABORA_CB'),
    ('scripts/BUSINESS/15_PERFORMANCE_MANAGEMENT_CRM', 'scripts/BUSINESS/15_PERFORMANCE_MANAGEMENT_CRM'),
    ('scripts/BUSINESS/CAMPAGNE', 'scripts/BUSINESS/CAMPAGNE'),
    ('scripts/CONSUMER/common', 'scripts/CONSUMER/common'),
    ('scripts/CONSUMER/config', 'scripts/CONSUMER/config'),
    ('scripts/CONSUMER/01_FORMATTA_PEDONALITA', 'scripts/CONSUMER/01_FORMATTA_PEDONALITA'),
    ('scripts/CONSUMER/02_REPORT_PEDONALITA', 'scripts/CONSUMER/02_REPORT_PEDONALITA'),
    ('scripts/CONSUMER/03_FORMATTA_MAGAZZINO', 'scripts/CONSUMER/03_FORMATTA_MAGAZZINO'),
    ('scripts/CONSUMER/11_CRUSCOTTO_AGGREGATIVO', 'scripts/CONSUMER/11_CRUSCOTTO_AGGREGATIVO'),
    ('scripts/CONSUMER/12_CRUSCOTTO_PISTA_CONSUMER', 'scripts/CONSUMER/12_CRUSCOTTO_PISTA_CONSUMER'),
    ('scripts/CONSUMER/13_REPORT_GIACENZE', 'scripts/CONSUMER/13_REPORT_GIACENZE'),
]

asset_collector = runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'packaging_assets.py'))
script_datas = asset_collector['script_assets'](script_datas, os.path.dirname(os.path.abspath(SPEC)))

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
