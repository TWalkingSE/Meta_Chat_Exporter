"""
Testes que confirmam o alinhamento da versão mínima de Python (Requirement 5).

Lê a versão mínima declarada em `pyproject.toml` (`requires-python`) e a versão
documentada no `README.md` ("Python X.Y ou superior.") e verifica que ambas
declaram a mesma versão mínima.
"""

import os
import re
import sys
import tomllib
import unittest
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Raiz do projeto resolvida em relação a este arquivo de teste
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
README_PATH = PROJECT_ROOT / "README.md"


def _versao_minima_pyproject() -> tuple[int, int]:
    """Extrai a versão mínima (major, minor) de `requires-python` no pyproject.toml."""
    with PYPROJECT_PATH.open("rb") as fp:
        data = tomllib.load(fp)
    requires_python = data["project"]["requires-python"]
    # Aceita formatos como ">=3.12", ">= 3.12", "==3.12"
    match = re.search(r"(\d+)\.(\d+)", requires_python)
    assert match is not None, f"requires-python sem versão reconhecível: {requires_python!r}"
    return int(match.group(1)), int(match.group(2))


def _versao_minima_readme() -> tuple[int, int]:
    """Extrai a versão mínima (major, minor) da linha 'Python X.Y ou superior.' no README."""
    texto = README_PATH.read_text(encoding="utf-8")
    # Procura especificamente o padrão "Python X.Y ou superior"
    match = re.search(r"Python\s+(\d+)\.(\d+)\s+ou\s+superior", texto)
    assert match is not None, "Linha 'Python X.Y ou superior' não encontrada no README.md"
    return int(match.group(1)), int(match.group(2))


class TestVersaoMinimaPython(unittest.TestCase):
    """Testes de exemplo para o alinhamento da versão mínima de Python."""

    def test_arquivos_existem(self):
        """Os arquivos de origem das versões devem existir."""
        self.assertTrue(PYPROJECT_PATH.is_file(), "pyproject.toml não encontrado")
        self.assertTrue(README_PATH.is_file(), "README.md não encontrado")

    def test_versao_minima_alinhada(self):
        """A versão mínima do pyproject.toml e do README.md deve ser a mesma (Requirement 5.1)."""
        versao_pyproject = _versao_minima_pyproject()
        versao_readme = _versao_minima_readme()
        self.assertEqual(
            versao_pyproject,
            versao_readme,
            f"Versão mínima divergente: pyproject.toml={versao_pyproject} "
            f"vs README.md={versao_readme}",
        )

    def test_versao_minima_esperada(self):
        """Confirma que a versão mínima declarada é 3.12 em ambos os arquivos."""
        self.assertEqual(_versao_minima_pyproject(), (3, 12))
        self.assertEqual(_versao_minima_readme(), (3, 12))


if __name__ == "__main__":
    unittest.main()
