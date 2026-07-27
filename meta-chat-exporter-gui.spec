# -*- mode: python ; coding: utf-8 -*-
"""
Configuração de empacotamento PyInstaller para a GUI e CLI do Meta Chat Exporter.

Gera dois executáveis:
  - chat-exporter-gui.exe  (GUI PyQt6, sem console)
  - chat-exporter.exe      (CLI, com console)

Como construir (no Windows, com o ambiente de desenvolvimento instalado):

    pip install -e ".[dev]"
    pyinstaller meta-chat-exporter-gui.spec

Os executáveis finais são gerados em ``dist/``.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).resolve()
SRC_DIR = PROJECT_ROOT / "src"

PKG = "meta_chat_exporter"
PROJECT_MODULES = [
    f"{PKG}.__init__",
    f"{PKG}.advanced_stats_schema",
    f"{PKG}.app",
    f"{PKG}.cli",
    f"{PKG}.config",
    f"{PKG}.consolidation",
    f"{PKG}.constants",
    f"{PKG}.exporters",
    f"{PKG}.generators_all",
    f"{PKG}.generators_base",
    f"{PKG}.generators_single",
    f"{PKG}.generic_parser",
    f"{PKG}.inject_transcriptions",
    f"{PKG}.manifest",
    f"{PKG}.media_parser",
    f"{PKG}.models",
    f"{PKG}.parser",
    f"{PKG}.redaction",
    f"{PKG}.safe_cache",
    f"{PKG}.services",
    f"{PKG}.stats",
    f"{PKG}.stats_investigation",
    f"{PKG}.stats_report",
    f"{PKG}.templates_all",
    f"{PKG}.transcriber",
    f"{PKG}.i18n",
    f"{PKG}.i18n.detection",
    f"{PKG}.i18n.en",
    f"{PKG}.i18n.pt",
    f"{PKG}.utils",
    f"{PKG}.widgets",
]

hidden_imports = list(PROJECT_MODULES)
for _pyqt_mod in ("PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"):
    hidden_imports += collect_submodules(_pyqt_mod)

block_cipher = None

# --- GUI build (windowed, sem console) ---
gui_a = Analysis(
    [str(SRC_DIR / PKG / "app.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "torch",
        "torchvision",
        "torchaudio",
        "whisper",
        "numba",
        "llvmlite",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

gui_pyz = PYZ(gui_a.pure, gui_a.zipped_data, cipher=block_cipher)

gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
    gui_a.binaries,
    gui_a.zipfiles,
    gui_a.datas,
    [],
    name="chat-exporter-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# --- CLI build (com console) ---
cli_a = Analysis(
    [str(SRC_DIR / PKG / "cli.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PyQt6",
        "torch",
        "torchvision",
        "torchaudio",
        "whisper",
        "numba",
        "llvmlite",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

cli_pyz = PYZ(cli_a.pure, cli_a.zipped_data, cipher=block_cipher)

cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    cli_a.binaries,
    cli_a.zipfiles,
    cli_a.datas,
    [],
    name="chat-exporter",
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
