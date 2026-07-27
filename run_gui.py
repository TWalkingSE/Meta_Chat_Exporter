#!/usr/bin/env python3
"""
Atalho para abrir a interface gráfica a partir da raiz do projeto.

Com o layout de pacote `src/`, o módulo da GUI vive em
`src/meta_chat_exporter/app.py` e não pode ser executado diretamente como
`python app.py`. Este atalho importa o pacote pelo nome (instalado via
`pip install -e .`) e chama o ponto de entrada da GUI.

Uso:
    python run_gui.py

Equivalente a:
    venv\\Scripts\\chat-exporter-gui.exe
    python -m meta_chat_exporter.app
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_VENV_PYTHON = _ROOT / "venv" / "Scripts" / "python.exe"
if _VENV_PYTHON.exists() and Path(sys.executable).resolve() != _VENV_PYTHON.resolve():
    os.execv(
        str(_VENV_PYTHON),
        [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]],
    )

_SRC = _ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    from meta_chat_exporter.app import main
except ModuleNotFoundError as e:
    if e.name == "PyQt6":
        raise SystemExit(
            "PyQt6 não encontrado. Execute com o venv do projeto ou instale as dependências."
        ) from e
    raise

if __name__ == "__main__":
    main()
