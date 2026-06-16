# PyInstaller spec — 단일 실행 파일(서버 + 대시보드 정적파일 포함)
# 빌드:  pyinstaller bhist.spec   →  dist/bhist  (Windows: dist/bhist.exe)
#
# 주의: 크로스 빌드는 불가하다. Windows .exe는 Windows에서, macOS 앱은 macOS에서 빌드해야 한다.

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['app_entry.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('server/static', 'static'),           # 대시보드/매니페스트/아이콘 번들
        ('collector/schema.sql', 'collector'),  # DB 스키마(런타임에 읽음)
    ],
    hiddenimports=collect_submodules('server') + collect_submodules('collector'),
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='bhist',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=True,
)
