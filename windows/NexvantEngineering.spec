# Build on Windows with: python -m PyInstaller --clean --noconfirm windows/NexvantEngineering.spec
from pathlib import Path

root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "windows" / "desktop.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / "static"), "static")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
archive = PYZ(analysis.pure)
exe = EXE(
    archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="NexvantEngineering",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
