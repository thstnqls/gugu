# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for GUGU (macOS .app)

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
        'AppKit',
        'Quartz',
        'objc',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='GUGU',
)

app = BUNDLE(
    coll,
    name='GUGU.app',
    icon=str(project_dir / 'build' / 'AppIcon.icns'),
    bundle_identifier='com.local.pigeonpecker',
    version=APP_VERSION,
    info_plist={
        'CFBundleName': 'GUGU',
        'CFBundleDisplayName': 'GUGU',
        'CFBundleShortVersionString': APP_VERSION,
        'CFBundleVersion': APP_VERSION,
        'LSMinimumSystemVersion': '11.0',
        # 메뉴바 트레이 전용 (Dock 아이콘 안 띄움)
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
        # 클릭을 다른 앱으로 전달하기 위한 권한 / 안내 문구
        'NSAppleEventsUsageDescription': '비둘기가 마우스를 따라다니기 위해 필요합니다.',
    },
)
