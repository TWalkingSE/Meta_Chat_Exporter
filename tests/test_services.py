"""
Testes para o módulo services.py - CacheService e ExportService

Estes testes validam os serviços isolados da camada de interface (GUI) SEM
instanciar PyQt nem importar app.py. Cobrem o comportamento observável de
cache e exportação (Requisitos 27.1, 27.2, 27.3).
"""

import csv
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.models import Message, Participant, ProfileMedia, Thread
from meta_chat_exporter.services import CacheService, ExportService

# --- Fábricas de dados sintéticos (sem dependência de PyQt) ---


def _make_msg(author="user2", author_id="200", body="Olá mundo", sent=None):
    """Cria uma Message sintética mínima."""
    return Message(
        author=author,
        author_id=author_id,
        platform="instagram",
        sent=sent or datetime(2024, 1, 15, 10, 0, 0),
        body=body,
        source_file="test.html",
    )


def _make_thread(thread_id="t1", name="Conversa Teste", messages=None):
    """Cria um Thread sintético com participantes (dono + um contato)."""
    return Thread(
        thread_id=thread_id,
        thread_name=name,
        participants=[
            Participant("owner_user", "instagram", "100"),
            Participant("user2", "instagram", "200"),
        ],
        messages=messages if messages is not None else [_make_msg()],
    )


def _make_html_files(base: Path, count=2):
    """Cria arquivos .html reais para alimentar as chaves de cache."""
    files = []
    for i in range(count):
        f = base / f"arquivo_{i}.html"
        f.write_text(f"<html>conteudo {i}</html>", encoding="utf-8")
        files.append(f)
    return files


class TestCacheService(unittest.TestCase):
    """Testes do serviço de cache isolado da GUI (Requisito 27.1)."""

    def setUp(self):
        self.service = CacheService()

    def test_get_cache_dir_cria_diretorio(self):
        """get_cache_dir deve criar o diretório de cache se ausente."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = _make_html_files(base)
            cache_dir = base / CacheService.CACHE_DIR_NAME
            self.assertFalse(cache_dir.exists())

            result = self.service.get_cache_dir(files)

            self.assertTrue(result.exists())
            self.assertTrue(result.is_dir())
            self.assertEqual(result, cache_dir)

    def test_cache_key_estavel_para_mesmos_arquivos(self):
        """A chave de cache deve ser idêntica para os mesmos arquivos inalterados."""
        with TemporaryDirectory() as tmp:
            files = _make_html_files(Path(tmp))
            key1 = self.service.get_cache_key(files)
            key2 = self.service.get_cache_key(files)
            self.assertEqual(key1, key2)

    def test_cache_key_muda_quando_arquivo_muda(self):
        """A chave de cache deve mudar quando o conteúdo (tamanho) de um arquivo muda."""
        with TemporaryDirectory() as tmp:
            files = _make_html_files(Path(tmp))
            key_antes = self.service.get_cache_key(files)

            # Alterar o tamanho do primeiro arquivo invalida a chave
            files[0].write_text("<html>conteudo bem maior do que antes</html>", encoding="utf-8")
            key_depois = self.service.get_cache_key(files)

            self.assertNotEqual(key_antes, key_depois)

    def test_file_cache_key_muda_por_arquivo(self):
        """get_file_cache_key deve gerar chaves distintas para arquivos distintos."""
        with TemporaryDirectory() as tmp:
            files = _make_html_files(Path(tmp))
            k0 = self.service.get_file_cache_key(files[0])
            k1 = self.service.get_file_cache_key(files[1])
            self.assertNotEqual(k0, k1)

    def test_round_trip_save_load_to_cache(self):
        """save_to_cache/load_from_cache devem preservar os dados consolidados."""
        with TemporaryDirectory() as tmp:
            files = _make_html_files(Path(tmp))
            thread = _make_thread()
            data = {
                "threads": [thread],
                "owner_username": "owner_user",
                "owner_id": "100",
            }

            size_mb = self.service.save_to_cache(files, data)
            self.assertIsNotNone(size_mb)
            self.assertGreaterEqual(size_mb, 0.0)

            loaded = self.service.load_from_cache(files)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["owner_username"], "owner_user")
            self.assertEqual(loaded["owner_id"], "100")
            self.assertEqual(len(loaded["threads"]), 1)

            loaded_thread = loaded["threads"][0]
            self.assertIsInstance(loaded_thread, Thread)
            self.assertEqual(loaded_thread.thread_id, thread.thread_id)
            self.assertEqual(loaded_thread.thread_name, thread.thread_name)
            self.assertEqual(len(loaded_thread.messages), 1)
            self.assertEqual(loaded_thread.messages[0].author, "user2")

    def test_load_from_cache_inexistente_retorna_none(self):
        """load_from_cache deve retornar None quando não há cache salvo."""
        with TemporaryDirectory() as tmp:
            files = _make_html_files(Path(tmp))
            self.assertIsNone(self.service.load_from_cache(files))

    def test_file_cache_round_trip(self):
        """save_file_cache/load_file_cache devem preservar o cache por arquivo."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            files = _make_html_files(base)
            cache_dir = self.service.get_cache_dir(files)

            payload = {"valor": 42, "nome": "teste"}
            self.service.save_file_cache(files[0], cache_dir, payload)

            loaded = self.service.load_file_cache(files[0], cache_dir)
            self.assertEqual(loaded, payload)


class TestExportService(unittest.TestCase):
    """Testes do serviço de exportação isolado da GUI (Requisito 27.2)."""

    def setUp(self):
        self.service = ExportService()

    def test_export_json_gera_arquivo(self):
        """export_json deve gerar um arquivo JSON válido com meta e conversas."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            threads = [_make_thread(messages=[_make_msg(), _make_msg(author="owner_user")])]

            output_path, filename = self.service.export_json(threads, "owner_user", "100", base)

            self.assertTrue(output_path.exists())
            self.assertTrue(filename.endswith(".json"))
            with open(output_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertIn("meta", data)
            self.assertIn("conversas", data)
            self.assertEqual(data["meta"]["total_conversas"], 1)

    def test_export_csv_gera_arquivos(self):
        """export_csv deve gerar o CSV de mensagens e o CSV de estatísticas."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            threads = [
                _make_thread(messages=[_make_msg(body="primeira"), _make_msg(body="segunda")])
            ]

            output_path, filename, stats_path, stats_filename = self.service.export_csv(
                threads, "owner_user", "100", base
            )

            self.assertTrue(output_path.exists())
            self.assertTrue(filename.endswith(".csv"))
            self.assertTrue(stats_filename.endswith("_stats.csv"))

            with open(output_path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 2)
            self.assertIn("autor", rows[0])
            self.assertIn("corpo", rows[0])

    def test_export_all_html_gera_arquivo(self):
        """export_all_html deve gerar um arquivo HTML não vazio."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            threads = [_make_thread()]

            output_path, filename = self.service.export_all_html(
                threads, "owner_user", "100", {}, ProfileMedia(), base
            )

            self.assertTrue(output_path.exists())
            self.assertTrue(filename.endswith(".html"))
            content = output_path.read_text(encoding="utf-8")
            self.assertGreater(len(content), 0)
            self.assertIn("<html", content.lower())

    def test_export_all_html_redact_nao_muta_threads_originais(self):
        """Com redact=True, a lista de threads original NÃO deve ser mutada (deepcopy)."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            msg = _make_msg(author="user2", author_id="200")
            thread = _make_thread(name="Conversa Original", messages=[msg])
            threads = [thread]

            # Snapshot dos valores sensíveis antes da exportação redigida
            autor_antes = thread.messages[0].author
            autor_id_antes = thread.messages[0].author_id
            nome_antes = thread.thread_name
            participantes_antes = [p.username for p in thread.participants]

            output_path, _ = self.service.export_all_html(
                threads, "owner_user", "100", {}, ProfileMedia(), base, redact=True
            )

            self.assertTrue(output_path.exists())

            # Os objetos originais devem permanecer inalterados pois a redação
            # opera sobre uma cópia profunda (deepcopy).
            self.assertEqual(thread.messages[0].author, autor_antes)
            self.assertEqual(thread.messages[0].author, "user2")
            self.assertEqual(thread.messages[0].author_id, autor_id_antes)
            self.assertEqual(thread.thread_name, nome_antes)
            self.assertEqual([p.username for p in thread.participants], participantes_antes)

    def test_export_all_html_sem_redact_usa_threads_originais(self):
        """Sem redact, os nomes originais devem aparecer no HTML gerado."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            threads = [_make_thread(name="Conversa Visivel")]

            output_path, _ = self.service.export_all_html(
                threads, "owner_user", "100", {}, ProfileMedia(), base, redact=False
            )

            content = output_path.read_text(encoding="utf-8")
            self.assertNotIn("Conversa Redigida", content)

    def test_export_thread_html_gera_arquivo(self):
        """export_thread_html deve gerar um arquivo HTML individual não vazio."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            thread = _make_thread(messages=[_make_msg(), _make_msg(author="owner_user")])

            output_path, filename = self.service.export_thread_html(
                thread, "owner_user", "100", {}, base
            )

            self.assertTrue(output_path.exists())
            self.assertTrue(filename.startswith("chat_"))
            self.assertTrue(filename.endswith(".html"))
            content = output_path.read_text(encoding="utf-8")
            self.assertGreater(len(content), 0)
            self.assertIn("<html", content.lower())

    def test_export_thread_html_redact_nao_muta_original(self):
        """Com redact=True, o thread original NÃO deve ser mutado (deepcopy)."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            msg = _make_msg(author="user2", author_id="200")
            thread = _make_thread(name="Conversa Original", messages=[msg])

            autor_antes = thread.messages[0].author
            autor_id_antes = thread.messages[0].author_id
            nome_antes = thread.thread_name

            output_path, filename = self.service.export_thread_html(
                thread, "owner_user", "100", {}, base, redact=True
            )

            self.assertTrue(output_path.exists())
            self.assertIn("_redigido", filename)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("Conversa Redigida", content)

            # Original thread unchanged
            self.assertEqual(thread.messages[0].author, autor_antes)
            self.assertEqual(thread.messages[0].author_id, autor_id_antes)
            self.assertEqual(thread.thread_name, nome_antes)

    def test_export_thread_html_grava_manifesto(self):
        """export_thread_html deve gravar um manifesto de custódia quando há fontes."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            # Create a source HTML file so manifest has something to hash
            (base / "source.html").write_text("<html>meta source</html>", encoding="utf-8")
            thread = _make_thread()

            output_path, _ = self.service.export_thread_html(
                thread, "owner_user", "100", {}, base
            )

            self.assertTrue(output_path.exists())
            # Check that a manifest file was created
            manifest_files = list(base.glob("manifesto_chat_*.json"))
            self.assertEqual(len(manifest_files), 1)
            import json as _json

            manifest = _json.loads(manifest_files[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema"], "meta-chat-exporter.custody_manifest.v1")
            self.assertGreaterEqual(manifest["meta"]["source_count"], 1)

    def test_export_thread_html_sem_manifesto(self):
        """export_thread_html com write_manifest=False não deve gerar manifesto."""
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            thread = _make_thread()

            output_path, _ = self.service.export_thread_html(
                thread, "owner_user", "100", {}, base, write_manifest=False
            )

            self.assertTrue(output_path.exists())
            manifest_files = list(base.glob("manifesto_chat_*.json"))
            self.assertEqual(len(manifest_files), 0)


if __name__ == "__main__":
    unittest.main()
