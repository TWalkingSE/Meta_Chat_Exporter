"""
Testes para o módulo stats.py - Estatísticas e Analytics
"""

import sys
import os
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Thread, Message, Attachment, Participant
from stats import ChatStatistics


def _make_msg(author="user1", body="Hello", sent=None, attachments=None,
              is_call=False, call_type="", call_duration=0, call_missed=False,
              is_reaction=False, has_payment=False, subscription_event="",
              subscription_users=None, disappearing=False, share_url=None,
              removed_by_sender=False):
    """Helper para criar mensagens de teste"""
    return Message(
        author=author,
        author_id="100",
        platform="instagram",
        sent=sent or datetime(2024, 1, 15, 10, 0, 0),
        body=body,
        disappearing=disappearing,
        disappearing_duration="",
        attachments=attachments or [],
        share_url=share_url,
        share_text=None,
        is_call=is_call,
        call_type=call_type,
        call_duration=call_duration,
        call_missed=call_missed,
        removed_by_sender=removed_by_sender,
        source_file="test.html",
        is_reaction=is_reaction,
        subscription_event=subscription_event,
        subscription_users=subscription_users or [],
        has_payment=has_payment,
    )


def _make_thread(thread_id="1", name="Test Chat", participants=None, messages=None):
    """Helper para criar threads de teste"""
    return Thread(
        thread_id=thread_id,
        thread_name=name,
        participants=participants or [Participant("user1", "instagram", "100"),
                                       Participant("user2", "instagram", "200")],
        messages=messages or [],
    )


class TestEmojiStats(unittest.TestCase):
    """Testes para estatísticas de emojis"""

    def test_emoji_detection(self):
        msgs = [
            _make_msg(body="Olá 😀👍", author="user1"),
            _make_msg(body="Tudo bem? 🎉🎉🎉", author="user2"),
            _make_msg(body="Sem emoji aqui", author="user1"),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread], "user1", "100")
        result = stats.generate_all()
        emojis = result["emojis"]

        self.assertGreater(emojis["total_emojis"], 0)
        self.assertGreater(emojis["emojis_unicos"], 0)
        self.assertEqual(emojis["msgs_com_emoji"], 2)
        self.assertIn("top_30", emojis)

    def test_no_emojis(self):
        msgs = [_make_msg(body="Hello world"), _make_msg(body="No emojis here")]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        self.assertEqual(result["emojis"]["total_emojis"], 0)

    def test_emoji_per_author(self):
        msgs = [
            _make_msg(body="😀😀😀", author="user1"),
            _make_msg(body="👍", author="user2"),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        por_autor = result["emojis"]["por_autor"]
        # por_autor is a list of dicts with 'nome', 'total', 'top_3'
        self.assertIsInstance(por_autor, list)
        names = [a["nome"] for a in por_autor]
        self.assertIn("user1", names)
        user1_data = next(a for a in por_autor if a["nome"] == "user1")
        user2_data = next(a for a in por_autor if a["nome"] == "user2")
        self.assertGreater(user1_data["total"], user2_data["total"])


class TestIntegrityCheck(unittest.TestCase):
    """Testes para verificação de integridade de anexos"""

    def test_no_attachments(self):
        msgs = [_make_msg(body="Hello")]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        integrity = result["integridade_anexos"]
        self.assertEqual(integrity["total"], 0)
        self.assertEqual(integrity["percentual_ok"], 0)

    def test_with_missing_attachment(self):
        att = Attachment(filename="missing.jpg", file_type="image",
                        size=0, url="", local_path="nonexistent/path/missing.jpg")
        msgs = [_make_msg(attachments=[att])]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        integrity = result["integridade_anexos"]
        self.assertEqual(integrity["total"], 1)
        self.assertEqual(integrity["faltando"], 1)


class TestGapDetection(unittest.TestCase):
    """Testes para detecção de gaps de inatividade"""

    def test_no_gaps(self):
        msgs = [
            _make_msg(sent=datetime(2024, 1, 1)),
            _make_msg(sent=datetime(2024, 1, 10)),
            _make_msg(sent=datetime(2024, 1, 20)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        self.assertEqual(result["gaps"]["total_gaps"], 0)

    def test_gap_detected(self):
        msgs = [
            _make_msg(sent=datetime(2024, 1, 1)),
            _make_msg(sent=datetime(2024, 6, 1)),  # 151 dias depois
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        self.assertGreater(result["gaps"]["total_gaps"], 0)
        self.assertGreaterEqual(result["gaps"]["gaps"][0]["dias"], 30)


class TestRelationshipGraph(unittest.TestCase):
    """Testes para grafo de relacionamentos"""

    def test_empty_threads(self):
        stats = ChatStatistics([])
        result = stats.generate_all()
        self.assertEqual(result["grafo"]["svg"], "")

    def test_graph_generation(self):
        msgs = [_make_msg(author="user1"), _make_msg(author="user2")]
        t1 = _make_thread(messages=msgs, participants=[
            Participant("user1", "ig", "1"), Participant("user2", "ig", "2")
        ])
        t2 = _make_thread(thread_id="2", messages=msgs, participants=[
            Participant("user1", "ig", "1"), Participant("user3", "ig", "3")
        ])
        stats = ChatStatistics([t1, t2])
        result = stats.generate_all()
        self.assertIn("<svg", result["grafo"]["svg"])
        self.assertGreater(result["grafo"]["total_nos"], 0)


class TestMessageLengthDistribution(unittest.TestCase):
    """Testes para distribuição de tamanho das mensagens"""

    def test_distribution(self):
        msgs = [
            _make_msg(body="Hi"),             # 0-10
            _make_msg(body="A" * 100),         # 51-150
            _make_msg(body="B" * 600),         # 501-1000
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        dist = result["tamanho_msgs"]["distribuicao"]
        self.assertGreater(dist["0-10"], 0)
        self.assertGreater(dist["51-150"], 0)
        self.assertGreater(dist["501-1000"], 0)

    def test_avg_chars(self):
        msgs = [
            _make_msg(body="A" * 10),
            _make_msg(body="A" * 20),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        self.assertEqual(result["tamanho_msgs"]["media_chars"], 15.0)


class TestPeriodComparison(unittest.TestCase):
    """Testes para comparação entre períodos"""

    def test_comparison_inactive(self):
        msgs = [_make_msg(sent=None)]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        self.assertFalse(result["comparacao_periodos"]["ativo"])

    def test_comparison_active(self):
        msgs = [
            _make_msg(sent=datetime(2024, 1, 1), author="user1"),
            _make_msg(sent=datetime(2024, 3, 1), author="user1"),
            _make_msg(sent=datetime(2024, 6, 1), author="user1"),
            _make_msg(sent=datetime(2024, 12, 1), author="user1"),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        comp = result["comparacao_periodos"]
        self.assertTrue(comp["ativo"])
        self.assertIn("p1", comp)
        self.assertIn("p2", comp)
        self.assertIn("variacoes", comp)


class TestLanguageDetection(unittest.TestCase):
    """Testes para detecção de idioma"""

    def test_portuguese(self):
        msgs = [
            _make_msg(body="Olá, tudo bem? Isso é muito bom para todos nós"),
            _make_msg(body="Não sei como fazer isso mas acho que vai dar certo"),
            _make_msg(body="Também penso assim, está muito bem obrigado"),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        self.assertEqual(result["idiomas"]["principal"], "Português")
        self.assertIn(result["idiomas"]["metodo"], {"keywords", "langdetect"})

    def test_english(self):
        msgs = [
            _make_msg(body="Hello, how are you? I think this is great for everyone"),
            _make_msg(body="Yeah I know what you mean, just about right"),
            _make_msg(body="Would have been there but they had their own plans"),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()
        self.assertEqual(result["idiomas"]["principal"], "English")
        self.assertIn(result["idiomas"]["metodo"], {"keywords", "langdetect"})


class TestHTMLReport(unittest.TestCase):
    """Testes para geração do relatório HTML"""

    def test_report_generation(self):
        msgs = [
            _make_msg(body="Hello 😀", author="user1", sent=datetime(2024, 1, 15, 10, 0)),
            _make_msg(body="Hi there 👍", author="user2", sent=datetime(2024, 1, 15, 11, 0)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread], "user1", "100")
        html = stats.generate_html_report()
        self.assertIn("stats-panel", html)
        self.assertIn("Resumo Geral", html)
        self.assertIn("Top Participantes", html)

    def test_css_generation(self):
        css = ChatStatistics.get_stats_css()
        self.assertIn(".stats-panel", css)
        self.assertIn(".stat-card", css)
        self.assertIn(".gap-item", css)
        self.assertIn(".msg-len-chart", css)
        self.assertIn(".comp-table", css)
        self.assertIn(".integrity-stats", css)

    def test_js_generation(self):
        js = ChatStatistics.get_stats_js()
        self.assertIn("toggleStatsPanel", js)


class TestGenerateAll(unittest.TestCase):
    """Testes para generate_all() - verifica todas as chaves retornadas"""

    def test_all_keys_present(self):
        msgs = [_make_msg()]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()

        expected_keys = [
            "resumo", "por_participante", "por_conversa", "temporal",
            "midias", "chamadas", "palavras", "horarios", "top_conversas",
            "tempo_resposta", "heatmap", "reacoes", "emojis",
            "integridade_anexos", "gaps", "grafo", "tamanho_msgs",
            "comparacao_periodos", "idiomas",
        ]
        for key in expected_keys:
            self.assertIn(key, result, f"Chave '{key}' ausente em generate_all()")


if __name__ == "__main__":
    unittest.main()
