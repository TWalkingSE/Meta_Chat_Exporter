"""
Testes para o módulo cli.py - Interface de linha de comando
"""

import argparse
import contextlib
import io
import json
import os
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter import constants
from meta_chat_exporter.cli import (
    _load_transcriptions,
    _print_comparacao_periodos,
    _print_emojis,
    _print_gaps,
    _print_heatmap,
    _print_idiomas,
    _print_tempo_resposta,
    cmd_export_csv,
    cmd_export_json,
    cmd_stats,
    process_folder,
)

_SAMPLE_HTML = """<html><body>
<div class="t">Account Identifier<div class="m"><div>owner</div></div></div>
<div id="property-unified_messages">
Thread<div class="m"><div>Conversa (12345678)
Current Participants<div class="m"><div>user1 (instagram: 100), user2 (instagram: 200)</div></div>
<div class="t o">Author<div class="m"><div>user1 (instagram: 100)</div></div>
Sent<div class="m"><div>2024-01-15 13:30:00 UTC</div></div>
Body<div class="m"><div>Hello World!</div></div><div class="p"></div></div>
</div>
<div id="property-other_section">
</div>
</body></html>"""


class TestProcessFolder(unittest.TestCase):
    def setUp(self):
        constants.set_timezone_offset(timedelta(hours=-3))
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_folder_returns_empty(self):
        threads, owner, owner_id = process_folder(self.dir)
        self.assertEqual(threads, [])
        self.assertEqual(owner, "")
        self.assertEqual(owner_id, "")

    def test_folder_with_valid_html(self):
        (self.dir / "records.html").write_text(_SAMPLE_HTML, encoding="utf-8")
        threads, owner, _ = process_folder(self.dir)
        self.assertEqual(len(threads), 1)
        self.assertEqual(owner, "owner")
        self.assertEqual(threads[0].thread_id, "12345678")

    def test_generated_files_are_skipped(self):
        # arquivos de saída não devem ser reprocessados como entrada
        (self.dir / "chat_foo.html").write_text(_SAMPLE_HTML, encoding="utf-8")
        (self.dir / "todas_conversas_x.html").write_text(_SAMPLE_HTML, encoding="utf-8")
        threads, _, _ = process_folder(self.dir)
        self.assertEqual(threads, [])


class TestCliCommands(unittest.TestCase):
    def setUp(self):
        constants.set_timezone_offset(timedelta(hours=-3))
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        (self.dir / "records.html").write_text(_SAMPLE_HTML, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_json_export_creates_file(self):
        out = self.dir / "out.json"
        args = argparse.Namespace(pasta=str(self.dir), output="out.json", estatisticas=False)
        rc = cmd_export_json(args)
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())

        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("conversas", data)
        self.assertEqual(len(data["conversas"]), 1)

    def test_csv_export_creates_file(self):
        out = self.dir / "out.csv"
        args = argparse.Namespace(pasta=str(self.dir), output="out.csv", estatisticas=False)
        rc = cmd_export_csv(args)
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())

    def test_stats_command_runs(self):
        args = argparse.Namespace(pasta=str(self.dir))
        rc = cmd_stats(args)
        self.assertEqual(rc, 0)

    def test_nonexistent_folder_returns_1(self):
        missing = str(self.dir / "nope")
        self.assertEqual(
            cmd_export_json(argparse.Namespace(pasta=missing, output=None, estatisticas=False)), 1
        )
        self.assertEqual(
            cmd_export_csv(argparse.Namespace(pasta=missing, output=None, estatisticas=False)), 1
        )
        self.assertEqual(cmd_stats(argparse.Namespace(pasta=missing)), 1)


class TestLoadTranscriptions(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_parses_basic_block(self):
        content = (
            "Nome: audio_1.mp3\n"
            "Caminho: linked_media/audio_1.mp3\n"
            "HASH: " + ("a" * 32) + "\n"
            "Olá, isto é um teste de transcrição.\n"
        )
        path = self.dir / "transc.txt"
        path.write_text(content, encoding="utf-8")

        result = _load_transcriptions(str(path))
        self.assertIn("audio_1.mp3", result)
        self.assertIn("teste de transcrição", result["audio_1.mp3"])

    def test_unreadable_returns_empty(self):
        result = _load_transcriptions(str(self.dir / "missing.txt"))
        self.assertEqual(result, {})


def _capturar(func, *args) -> str:
    """Executa `func(*args)` capturando o stdout e devolve o texto impresso."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        func(*args)
    return buffer.getvalue()


class TestStatsOutputHelpers(unittest.TestCase):
    """Testa as famílias de métricas exibidas pela CLI (R23.1, R23.2, R23.3).

    Cada helper deve exibir seu cabeçalho/rótulos quando há dados e indicar
    "sem dados" quando a métrica está vazia, sempre sem levantar exceção.
    """

    # --- Heatmap -------------------------------------------------------
    def test_heatmap_com_dados(self):
        heatmap = [[0] * 24 for _ in range(7)]
        heatmap[0][13] = 5  # Segunda, 13h
        heatmap[2][9] = 3  # Quarta, 9h
        saida = _capturar(_print_heatmap, heatmap)
        self.assertIn("Heatmap de Atividade", saida)
        self.assertIn("Dia mais ativo", saida)
        self.assertIn("Hora mais ativa", saida)
        self.assertNotIn("sem dados", saida)

    def test_heatmap_vazio(self):
        # Matriz toda zerada e None devem indicar ausência de dados sem erro
        self.assertIn("sem dados", _capturar(_print_heatmap, [[0] * 24 for _ in range(7)]))
        self.assertIn("sem dados", _capturar(_print_heatmap, None))

    # --- Emojis --------------------------------------------------------
    def test_emojis_com_dados(self):
        emojis = {
            "total_emojis": 12,
            "emojis_unicos": 2,
            "msgs_com_emoji": 7,
            "top_30": [{"emoji": "😀", "contagem": 8}, {"emoji": "🎉", "contagem": 4}],
        }
        saida = _capturar(_print_emojis, emojis)
        self.assertIn("Emojis", saida)
        self.assertIn("Top 10", saida)
        self.assertIn("😀", saida)
        self.assertNotIn("sem dados", saida)

    def test_emojis_vazio(self):
        self.assertIn("sem dados", _capturar(_print_emojis, {"top_30": []}))
        self.assertIn("sem dados", _capturar(_print_emojis, None))

    # --- Tempo de resposta --------------------------------------------
    def test_tempo_resposta_com_dados(self):
        tempo = [
            {
                "nome": "user1",
                "media_formatada": "2m 30s",
                "mediana_formatada": "1m 45s",
                "total_respostas": 42,
            }
        ]
        saida = _capturar(_print_tempo_resposta, tempo)
        self.assertIn("Tempo de Resposta", saida)
        self.assertIn("user1", saida)
        self.assertIn("mediana", saida)
        self.assertNotIn("sem dados", saida)

    def test_tempo_resposta_vazio(self):
        self.assertIn("sem dados", _capturar(_print_tempo_resposta, []))
        self.assertIn("sem dados", _capturar(_print_tempo_resposta, None))

    # --- Gaps ----------------------------------------------------------
    def test_gaps_com_dados(self):
        gaps = {
            "total_gaps": 2,
            "conversas_com_gaps": 1,
            "min_dias": 7,
            "maior_gap": {"dias": 30, "conversa": "Conversa X"},
            "gaps": [{"conversa": "Conversa X", "dias": 30}],
        }
        saida = _capturar(_print_gaps, gaps)
        self.assertIn("Gaps de Inatividade", saida)
        self.assertIn("Maior gap", saida)
        self.assertIn("Conversa X", saida)
        self.assertNotIn("sem dados", saida)

    def test_gaps_vazio(self):
        self.assertIn("sem dados", _capturar(_print_gaps, {"gaps": []}))
        self.assertIn("sem dados", _capturar(_print_gaps, None))

    # --- Idiomas -------------------------------------------------------
    def test_idiomas_com_dados(self):
        idiomas = {
            "principal": "Português",
            "metodo": "heuristica",
            "percentuais": {"Português": 80, "Inglês": 20},
        }
        saida = _capturar(_print_idiomas, idiomas)
        self.assertIn("Idiomas", saida)
        self.assertIn("Principal", saida)
        self.assertIn("Português", saida)
        self.assertNotIn("sem dados", saida)

    def test_idiomas_vazio(self):
        self.assertIn("sem dados", _capturar(_print_idiomas, {"percentuais": {}}))
        self.assertIn("sem dados", _capturar(_print_idiomas, None))

    # --- Comparação de períodos ---------------------------------------
    def test_comparacao_periodos_com_dados(self):
        comparacao = {
            "ativo": True,
            "p1_de": "2024-01-01",
            "p1_ate": "2024-03-31",
            "p2_de": "2024-04-01",
            "p2_ate": "2024-06-30",
            "p1": {"msgs": 100, "anexos": 10, "chamadas": 2, "autores": 3, "media_len": 25},
            "p2": {"msgs": 150, "anexos": 20, "chamadas": 5, "autores": 4, "media_len": 30},
            "variacoes": {
                "msgs": "+50%",
                "anexos": "+100%",
                "chamadas": "+150%",
                "autores": "+33%",
                "media_len": "+20%",
            },
        }
        saida = _capturar(_print_comparacao_periodos, comparacao)
        self.assertIn("Comparação de Períodos", saida)
        self.assertIn("Período 1", saida)
        self.assertIn("Mensagens", saida)
        self.assertNotIn("sem dados", saida)

    def test_comparacao_periodos_vazio(self):
        self.assertIn("sem dados", _capturar(_print_comparacao_periodos, {"ativo": False}))
        self.assertIn("sem dados", _capturar(_print_comparacao_periodos, None))


if __name__ == "__main__":
    unittest.main()
