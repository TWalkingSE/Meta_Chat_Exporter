"""
Smoke test de empacotamento (tarefa 33.2, Requirements 28.2, 28.3).

Verifica que a descoberta automática de pacotes configurada no ``pyproject.toml``
(layout ``src/`` com ``[tool.setuptools.packages.find]``) inclui o pacote
``meta_chat_exporter`` e todos os seus subpacotes/módulos no artefato, e que os
módulos referenciados pelos entry points de CLI/GUI são localizáveis. Usa
``importlib.util.find_spec`` para confirmar a presença no artefato sem importar
de fato cada módulo (evitando efeitos colaterais como a importação do PyQt6).
"""

import importlib.util
import os
import sys
import tomllib
import unittest
from pathlib import Path

from setuptools import find_packages

# Raiz do projeto e diretório de código-fonte (layout src/).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _PROJECT_ROOT / "src"
_PKG_DIR = _SRC_DIR / "meta_chat_exporter"

# Garante que o pacote seja importável a partir do layout src/ mesmo sem
# instalação editável (espelha o padrão usado pelos demais testes).
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _module_names_no_disco() -> set[str]:
    """Enumera os nomes de módulos (qualificados) presentes em disco no pacote."""
    nomes: set[str] = set()
    for raiz, _dirs, arquivos in os.walk(_PKG_DIR):
        rel = Path(raiz).relative_to(_SRC_DIR)
        pacote = ".".join(rel.parts)
        for arquivo in arquivos:
            if not arquivo.endswith(".py"):
                continue
            if arquivo == "__init__.py":
                # O próprio pacote já é validado via find_packages.
                continue
            nomes.add(f"{pacote}.{arquivo[:-3]}")
    return nomes


class TestPackagingDiscovery(unittest.TestCase):
    """Valida a descoberta automática de pacotes e a localização dos módulos."""

    def test_layout_src_existe(self):
        # O artefato segue o layout src/ com o pacote principal.
        self.assertTrue(_SRC_DIR.is_dir(), "diretório src/ ausente")
        self.assertTrue((_PKG_DIR / "__init__.py").is_file(), "pacote principal ausente")

    def test_pyproject_configura_descoberta_automatica(self):
        # O pyproject usa packages.find sobre src/ (sem py-modules manual).
        with open(_PROJECT_ROOT / "pyproject.toml", "rb") as f:
            cfg = tomllib.load(f)
        setuptools_cfg = cfg["tool"]["setuptools"]
        self.assertEqual(setuptools_cfg.get("package-dir"), {"": "src"})
        find_cfg = setuptools_cfg["packages"]["find"]
        self.assertEqual(find_cfg.get("where"), ["src"])
        # py-modules manual não deve mais existir (substituído pela descoberta).
        self.assertNotIn("py-modules", setuptools_cfg)

    def test_find_packages_inclui_pacote_e_subpacotes(self):
        # A descoberta automática inclui o pacote e o subpacote i18n.
        descobertos = set(find_packages(where=str(_SRC_DIR)))
        self.assertIn("meta_chat_exporter", descobertos)
        self.assertIn("meta_chat_exporter.i18n", descobertos)
        # Todo diretório-pacote em disco (com __init__.py) deve ser descoberto.
        esperados = set()
        for raiz, _dirs, arquivos in os.walk(_PKG_DIR):
            if "__init__.py" in arquivos:
                rel = Path(raiz).relative_to(_SRC_DIR)
                esperados.add(".".join(rel.parts))
        self.assertTrue(
            esperados.issubset(descobertos),
            f"pacotes não descobertos: {esperados - descobertos}",
        )

    def test_todos_os_modulos_estao_no_artefato(self):
        # Cada módulo .py do pacote é localizável (parte do artefato), sem
        # precisar importá-lo de fato (find_spec não executa o módulo).
        modulos = _module_names_no_disco()
        self.assertTrue(modulos, "nenhum módulo encontrado no pacote")
        faltando = [nome for nome in sorted(modulos) if importlib.util.find_spec(nome) is None]
        self.assertEqual(faltando, [], f"módulos não localizáveis no artefato: {faltando}")

    def test_entry_points_apontam_para_modulos_existentes(self):
        # Os módulos dos entry points de CLI e GUI são localizáveis no artefato.
        with open(_PROJECT_ROOT / "pyproject.toml", "rb") as f:
            cfg = tomllib.load(f)
        scripts = dict(cfg["project"].get("scripts", {}))
        scripts.update(cfg["project"].get("gui-scripts", {}))
        self.assertIn("chat-exporter", scripts)
        self.assertIn("chat-exporter-gui", scripts)
        for alvo in scripts.values():
            modulo, _, atributo = alvo.partition(":")
            self.assertTrue(modulo.startswith("meta_chat_exporter."), alvo)
            self.assertEqual(atributo, "main", alvo)
            self.assertIsNotNone(
                importlib.util.find_spec(modulo),
                f"módulo do entry point ausente: {modulo}",
            )


if __name__ == "__main__":
    unittest.main()
