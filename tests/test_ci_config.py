"""
Testes que validam a configuração do workflow de CI (.github/workflows/tests.yml).

Estes testes garantem que o pipeline de integração contínua continua executando
as verificações de qualidade exigidas (ruff e mypy) em uma matriz que cobre tanto
Windows quanto Linux. Eles falham caso alguém remova essas etapas do workflow.

Validates: Requirements 30.1, 30.3
"""

import os
import sys
import unittest
from pathlib import Path

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Resolver o caminho do workflow relativo a este arquivo de teste
# (raiz do projeto / .github/workflows/tests.yml)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "tests.yml"


class TestCIWorkflowConfig(unittest.TestCase):
    """Testes para a configuração do workflow de CI"""

    @classmethod
    def setUpClass(cls):
        """Ler o conteúdo do workflow uma única vez para todos os testes"""
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_workflow_file_exists(self):
        """O arquivo de workflow do CI deve existir na raiz do projeto"""
        self.assertTrue(
            WORKFLOW_PATH.is_file(),
            f"Workflow de CI não encontrado em {WORKFLOW_PATH}",
        )

    def test_runs_ruff_check(self):
        """O workflow deve executar `ruff check` (lint) — Requirement 30.1"""
        self.assertIn("ruff check", self.workflow_text)

    def test_runs_ruff_format_check(self):
        """O workflow deve executar `ruff format --check` (formatação) — Requirement 30.1"""
        self.assertIn("ruff format --check", self.workflow_text)

    def test_runs_mypy(self):
        """O workflow deve executar `mypy` (checagem de tipos) — Requirement 30.1"""
        self.assertIn("mypy", self.workflow_text)

    def test_matrix_includes_linux(self):
        """A matriz do CI deve incluir Linux (ubuntu-latest) — Requirement 30.3"""
        self.assertIn("ubuntu-latest", self.workflow_text)

    def test_matrix_includes_windows(self):
        """A matriz do CI deve incluir Windows (windows-latest) — Requirement 30.3"""
        self.assertIn("windows-latest", self.workflow_text)

    def test_matrix_uses_os_axis(self):
        """A matriz deve parametrizar o runner pelo eixo de sistema operacional"""
        # O job roda em ${{ matrix.os }} com os dois sistemas declarados na matriz
        self.assertIn("matrix.os", self.workflow_text)


if __name__ == "__main__":
    unittest.main()
