# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for GUGU (Windows .exe)
# 빌드:  pyinstaller GUGU-win.spec
# 결과:  dist\GUGU\GUGU.exe  (트레이 상주, 콘솔 창 없음)

import re
from pathlib import Path

block_cipher = None

project_dir = Path(SPECPATH)

_version_src = (project_dir / 'pigeon_pecker' / '__version__.py').read_text(encoding='utf-8')
APP_VERSION = re.search(r'__version__\s*=\s*"([^"]+)"', _version_src).group(1)

a = Analysis(
    ['run_app.py'],
    pathex=[str(project_dir)],
    binaries=[],
    datas=[
        # 스프라이트 시트 전부 포함
        (str(project_dir / 'pigeon_pecker' / 'assets'), 'pigeon_pecker/assets'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # macOS 전용 — Windows 빌드에선 제외 (없어도 코드가 분기 처리)
        'AppKit', 'Quartz', 'objc', 'Foundation', 'ApplicationServices',
        # 안 쓰는 Qt 모듈 빼서 용량 줄이기
        'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
        'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
        'PySide6.QtBluetooth', 'PySide6.QtCharts', 'PySide6.QtDataVisualization',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtNetwork',
        'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtPdf',
        'PySide6.QtPdfWidgets', 'PySide6.QtPositioning', 'PySide6.QtPrintSupport',
        'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickControls2',
        'PySide6.QtQuickWidgets', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
        'PySide6.QtSensors', 'PySide6.QtSerialBus', 'PySide6.QtSerialPort',
        'PySide6.QtSpatialAudio', 'PySide6.QtSql', 'PySide6.QtStateMachine',
        'PySide6.QtSvg', 'PySide6.QtSvgWidgets', 'PySide6.QtTest', 'PySide6.QtTextToSpeech',
        'PySide6.QtUiTools', 'PySide6.QtWebChannel', 'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebSockets',
        'PySide6.QtXml',
        'tkinter',
    ],
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
    name='GUGU',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 트레이 상주 — 콘솔 창 안 띄움
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_dir / 'build' / 'AppIcon.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GUGU',
)
