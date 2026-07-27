"""
Testes para o módulo stats.py - Estatísticas e Analytics
"""

import os
import statistics
import sys
import unittest
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlparse

from hypothesis import given, settings
from hypothesis import strategies as st

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.i18n import get_stop_words
from meta_chat_exporter.models import Attachment, Message, Participant, Thread
from meta_chat_exporter.stats import ChatStatistics
from meta_chat_exporter.stats_report import StatsReportRenderer
from tests.strategies import messages
from tests.strategies import threads as thread_strategy


def _make_msg(
    author="user1",
    body="Hello",
    sent=None,
    attachments=None,
    is_call=False,
    call_type="",
    call_duration=0,
    call_missed=False,
    is_reaction=False,
    has_payment=False,
    subscription_event="",
    subscription_users=None,
    disappearing=False,
    share_url=None,
    removed_by_sender=False,
):
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
        participants=participants
        or [Participant("user1", "instagram", "100"), Participant("user2", "instagram", "200")],
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

    def test_emoji_regex_fallback_path(self):
        """O caminho de fallback por regex (R24.3) conta emojis sem a biblioteca."""
        stats = ChatStatistics([_make_thread(messages=[])])
        # Exercita diretamente o regex interno, simulando a ausência da
        # biblioteca opcional de emojis.
        clusters = stats._RE_EMOJI.findall("Olá 😀👍 mundo 🎉")
        chars = [
            ch for cluster in clusters for ch in cluster if ch not in ("\ufe0f", "\u200d", "\ufe0e")
        ]
        self.assertEqual(set(chars), {"😀", "👍", "🎉"})

    def test_emoji_extraction_uses_fallback_when_library_absent(self):
        """Com a biblioteca ausente, _extract_emoji_clusters recorre ao regex (R24.3)."""
        from meta_chat_exporter import stats as stats_module

        original_available = stats_module.EMOJI_AVAILABLE
        original_lib = stats_module.emoji_lib
        try:
            stats_module.EMOJI_AVAILABLE = False
            stats_module.emoji_lib = None
            stats = ChatStatistics([_make_thread(messages=[])])
            clusters = stats._extract_emoji_clusters("tudo bem 😀🎉")
            chars = [
                ch
                for cluster in clusters
                for ch in cluster
                if ch not in ("\ufe0f", "\u200d", "\ufe0e")
            ]
            self.assertEqual(set(chars), {"😀", "🎉"})
        finally:
            stats_module.EMOJI_AVAILABLE = original_available
            stats_module.emoji_lib = original_lib

    def test_emoji_stats_degrade_without_library(self):
        """generate_all() produz estatísticas de emoji mesmo sem a biblioteca (R24.3)."""
        from meta_chat_exporter import stats as stats_module

        original_available = stats_module.EMOJI_AVAILABLE
        original_lib = stats_module.emoji_lib
        try:
            stats_module.EMOJI_AVAILABLE = False
            stats_module.emoji_lib = None
            msgs = [
                _make_msg(body="Olá 😀👍", author="user1"),
                _make_msg(body="Festa 🎉🎉", author="user2"),
            ]
            stats = ChatStatistics([_make_thread(messages=msgs)])
            emojis = stats.generate_all()["emojis"]
            self.assertGreater(emojis["total_emojis"], 0)
            self.assertEqual(emojis["msgs_com_emoji"], 2)
        finally:
            stats_module.EMOJI_AVAILABLE = original_available
            stats_module.emoji_lib = original_lib

    # Feature: melhorias-analise-e-projeto, Property R24.2/R24.3 (degradação graciosa):
    # com a biblioteca opcional `emoji` ausente, as estatísticas de emoji produzidas por
    # generate_all() nunca quebram o cálculo e são EQUIVALENTES ao caminho de fallback por
    # regex (_RE_EMOJI) para qualquer conjunto de corpos de mensagem gerados.
    # **Validates: Requirements 24.2, 24.3**
    @settings(max_examples=150, deadline=None)
    @given(
        st.lists(
            st.lists(
                st.sampled_from(
                    [
                        "ola",
                        "tudo",
                        "bem",
                        "festa",
                        "😀",
                        "👍",
                        "🎉",
                        "😂",
                        "🔥",
                        "🥳",
                        "❤️",
                        "👨‍👩‍👧",  # sequência ZWJ
                        "",
                    ]
                ),
                max_size=6,
            ).map(" ".join),
            max_size=8,
        )
    )
    def test_emoji_stats_equivalentes_ao_fallback_sem_biblioteca(self, bodies):
        """Sem a biblioteca `emoji`, generate_all() degrada para o regex de forma equivalente."""
        from meta_chat_exporter import stats as stats_module

        original_available = stats_module.EMOJI_AVAILABLE
        original_lib = stats_module.emoji_lib
        try:
            # Força a ausência da biblioteca opcional para exercitar o fallback (R24.3).
            stats_module.EMOJI_AVAILABLE = False
            stats_module.emoji_lib = None

            msgs = [_make_msg(body=body, author="user1") for body in bodies]
            stats = ChatStatistics([_make_thread(messages=msgs)])

            # Degradação graciosa: o cálculo não deve interromper na ausência da biblioteca.
            emojis = stats.generate_all()["emojis"]

            # Referência computada diretamente pelo regex de fallback, replicando a mesma
            # decomposição em caracteres usada por _stats_emojis (ignora modificadores).
            modifiers = ("\ufe0f", "\u200d", "\ufe0e")
            ref_counter = Counter()
            ref_msgs_with_emoji = 0
            for body in bodies:
                if not body:
                    continue
                found = stats_module.ChatStatistics._RE_EMOJI.findall(body)
                if found:
                    ref_msgs_with_emoji += 1
                    for cluster in found:
                        for ch in cluster:
                            if ch not in modifiers:
                                ref_counter[ch] += 1

            self.assertEqual(emojis["total_emojis"], sum(ref_counter.values()))
            self.assertEqual(emojis["emojis_unicos"], len(ref_counter))
            self.assertEqual(emojis["msgs_com_emoji"], ref_msgs_with_emoji)
        finally:
            stats_module.EMOJI_AVAILABLE = original_available
            stats_module.emoji_lib = original_lib


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
        att = Attachment(
            filename="missing.jpg",
            file_type="image",
            size=0,
            url="",
            local_path="nonexistent/path/missing.jpg",
        )
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
        # R26.1: estrutura pura, sem SVG. Sem dados → nodes/edges vazios.
        self.assertEqual(result["grafo"]["nodes"], [])
        self.assertEqual(result["grafo"]["edges"], [])
        self.assertNotIn("svg", result["grafo"])
        # R26.2: o renderer produz string vazia para estrutura vazia.
        self.assertEqual(StatsReportRenderer.render_graph_svg(result["grafo"]), "")

    def test_graph_generation(self):
        msgs = [_make_msg(author="user1"), _make_msg(author="user2")]
        t1 = _make_thread(
            messages=msgs,
            participants=[Participant("user1", "ig", "1"), Participant("user2", "ig", "2")],
        )
        t2 = _make_thread(
            thread_id="2",
            messages=msgs,
            participants=[Participant("user1", "ig", "1"), Participant("user3", "ig", "3")],
        )
        stats = ChatStatistics([t1, t2])
        result = stats.generate_all()
        grafo = result["grafo"]
        # R26.1/R26.3: dados estruturais, sem SVG embutido.
        self.assertNotIn("svg", grafo)
        self.assertGreater(len(grafo["nodes"]), 0)
        self.assertGreater(len(grafo["edges"]), 0)
        # R26.2: SVG derivado exclusivamente da estrutura.
        svg = StatsReportRenderer.render_graph_svg(grafo)
        self.assertIn("<svg", svg)

    def test_grafo_data_structure_and_weights(self):
        # 3 mensagens entre user1 e user2 numa DM
        msgs = [_make_msg(author="user1"), _make_msg(author="user2"), _make_msg(author="user1")]
        thread = _make_thread(
            messages=msgs,
            participants=[Participant("user1", "ig", "1"), Participant("user2", "ig", "2")],
        )
        stats = ChatStatistics([thread])
        grafo = stats._grafo_data()

        # Campos exatamente conforme o esquema compartilhado.
        self.assertEqual(set(grafo.keys()), {"nodes", "edges"})
        for node in grafo["nodes"]:
            self.assertEqual(set(node.keys()), {"nome", "peso"})
        for edge in grafo["edges"]:
            self.assertEqual(set(edge.keys()), {"a", "b", "peso"})

        nomes = {node["nome"] for node in grafo["nodes"]}
        self.assertEqual(nomes, {"user1", "user2"})
        # Peso de cada nó = total de mensagens da conversa (co-ocorrência).
        for node in grafo["nodes"]:
            self.assertEqual(node["peso"], len(msgs))
        # Uma aresta entre os dois participantes com peso = nº de mensagens.
        self.assertEqual(len(grafo["edges"]), 1)
        self.assertEqual(grafo["edges"][0]["peso"], len(msgs))

    def test_grafo_data_top_n_limit(self):
        # Cria N+5 threads DM, cada uma com um par distinto de participantes,
        # e verifica que _grafo_data limita aos top max_nodes nós.
        threads = []
        for i in range(20):
            a = f"userA{i}"
            b = f"userB{i}"
            # Volume crescente para distinguir o ranking por peso.
            msgs = [_make_msg(author=a) for _ in range(i + 1)]
            threads.append(
                _make_thread(
                    thread_id=str(i),
                    messages=msgs,
                    participants=[Participant(a, "ig", a), Participant(b, "ig", b)],
                )
            )
        stats = ChatStatistics(threads)
        grafo = stats._grafo_data(max_nodes=5)
        self.assertEqual(len(grafo["nodes"]), 5)
        # Apenas arestas entre nós retidos são mantidas.
        retidos = {node["nome"] for node in grafo["nodes"]}
        for edge in grafo["edges"]:
            self.assertIn(edge["a"], retidos)
            self.assertIn(edge["b"], retidos)

    def test_grafo_data_empty_input(self):
        stats = ChatStatistics([])
        grafo = stats._grafo_data()
        self.assertEqual(grafo, {"nodes": [], "edges": []})

    def test_render_graph_svg_accessibility(self):
        grafo = {
            "nodes": [
                {"nome": "user1", "peso": 10},
                {"nome": "user2", "peso": 5},
                {"nome": "user3", "peso": 3},
            ],
            "edges": [
                {"a": "user1", "b": "user2", "peso": 4},
                {"a": "user1", "b": "user3", "peso": 2},
            ],
        }
        svg = StatsReportRenderer.render_graph_svg(grafo)
        self.assertIn("<svg", svg)
        self.assertIn('role="img"', svg)
        self.assertIn("aria-label=", svg)
        self.assertIn("<title>", svg)

    def test_render_graph_svg_empty(self):
        self.assertEqual(StatsReportRenderer.render_graph_svg({"nodes": [], "edges": []}), "")
        # Nós presentes mas sem arestas → grafo insuficiente → string vazia.
        only_nodes = {"nodes": [{"nome": "user1", "peso": 1}], "edges": []}
        self.assertEqual(StatsReportRenderer.render_graph_svg(only_nodes), "")

    # Feature: melhorias-analise-e-projeto, Property 20: Dados do grafo são
    # estruturais e referenciam participantes reais — para qualquer conjunto de
    # threads, os dados do grafo contêm apenas nós e arestas estruturais (sem SVG)
    # cujas arestas referenciam nós retidos do topo.
    # Validates: Requirements 26.1, 26.2, 26.3
    @settings(max_examples=150, deadline=None)
    @given(st.lists(thread_strategy(), max_size=6))
    def test_grafo_data_e_estrutural_e_referencia_participantes(self, threads):
        max_nodes = 30
        stats = ChatStatistics(threads)
        grafo = stats.generate_all()["grafo"]

        # R26.1/R26.3: estrutura pura, exatamente os campos do esquema, sem SVG.
        self.assertEqual(set(grafo.keys()), {"nodes", "edges"})
        self.assertNotIn("svg", grafo)

        nodes = grafo["nodes"]
        edges = grafo["edges"]

        # R26.1: número de nós limitado a max_nodes.
        self.assertLessEqual(len(nodes), max_nodes)

        node_names = set()
        pesos = []
        for node in nodes:
            self.assertEqual(set(node.keys()), {"nome", "peso"})
            self.assertIsInstance(node["peso"], int)
            self.assertGreaterEqual(node["peso"], 0)
            node_names.add(node["nome"])
            pesos.append(node["peso"])

        # R26.1: ordenação por peso decrescente (não-crescente).
        self.assertEqual(pesos, sorted(pesos, reverse=True))

        # R26.3: cada aresta tem os campos do esquema, peso não-negativo e
        # ambos os extremos referenciam nós retidos do topo (participantes reais).
        for edge in edges:
            self.assertEqual(set(edge.keys()), {"a", "b", "peso"})
            self.assertIsInstance(edge["peso"], int)
            self.assertGreaterEqual(edge["peso"], 0)
            self.assertIn(edge["a"], node_names)
            self.assertIn(edge["b"], node_names)

        # R26.2: o SVG renderizado deriva exclusivamente da estrutura (sem erro);
        # estrutura vazia produz string vazia.
        svg = StatsReportRenderer.render_graph_svg(grafo)
        self.assertIsInstance(svg, str)
        if not nodes:
            self.assertEqual(edges, [])
            self.assertEqual(svg, "")


class TestMessageLengthDistribution(unittest.TestCase):
    """Testes para distribuição de tamanho das mensagens"""

    def test_distribution(self):
        msgs = [
            _make_msg(body="Hi"),  # 0-10
            _make_msg(body="A" * 100),  # 51-150
            _make_msg(body="B" * 600),  # 501-1000
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

    def test_idioma_fora_do_mapa_reportado_por_codigo(self):
        """Idioma detectado fora do mapa de exibição é reportado pelo código (R24.1)."""
        from meta_chat_exporter import stats as stats_module

        # Código deliberadamente ausente do mapa de exibição.
        out_of_map_code = "zz"
        self.assertNotIn(out_of_map_code, stats_module.ChatStatistics._LANG_CODE_MAP)

        class _FakeDetection:
            def __init__(self, lang, prob):
                self.lang = lang
                self.prob = prob

        def _fake_detect_langs(_text):
            return [_FakeDetection(out_of_map_code, 0.99)]

        original_detect = stats_module.detect_langs
        original_available = stats_module.LANGDETECT_AVAILABLE
        try:
            stats_module.detect_langs = _fake_detect_langs
            stats_module.LANGDETECT_AVAILABLE = True
            # Corpos longos o suficiente para formar chunks de detecção.
            msgs = [
                _make_msg(body="Conteudo suficientemente longo para detectar idioma numero um"),
                _make_msg(body="Outra mensagem longa o bastante para formar um chunk valido aqui"),
            ]
            stats = ChatStatistics([_make_thread(messages=msgs)])
            result = stats.generate_all()["idiomas"]
            self.assertEqual(result["metodo"], "langdetect")
            # O código bruto aparece como chave (principal/percentuais), não descartado.
            self.assertEqual(result["principal"], out_of_map_code)
            self.assertIn(out_of_map_code, result["percentuais"])
        finally:
            stats_module.detect_langs = original_detect
            stats_module.LANGDETECT_AVAILABLE = original_available


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


class TestPagamentosStats(unittest.TestCase):
    """Testes para estatísticas de pagamentos ao longo do tempo (R8)"""

    def test_no_payments(self):
        msgs = [_make_msg(body="Olá"), _make_msg(body="Tudo bem?")]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        pagamentos = stats.generate_all()["pagamentos"]
        self.assertEqual(pagamentos["total"], 0)
        self.assertEqual(pagamentos["por_periodo"], [])

    def test_payments_aggregated_by_period(self):
        msgs = [
            _make_msg(has_payment=True, sent=datetime(2024, 1, 10)),
            _make_msg(has_payment=True, sent=datetime(2024, 1, 20)),
            _make_msg(has_payment=True, sent=datetime(2024, 3, 5)),
            _make_msg(has_payment=False, sent=datetime(2024, 3, 6)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        pagamentos = stats.generate_all()["pagamentos"]

        self.assertEqual(pagamentos["total"], 3)
        # Ordenado cronologicamente
        self.assertEqual(
            pagamentos["por_periodo"],
            [
                {"periodo": "2024-01", "contagem": 2},
                {"periodo": "2024-03", "contagem": 1},
            ],
        )
        # Total iguala a soma das contagens por período
        soma = sum(item["contagem"] for item in pagamentos["por_periodo"])
        self.assertEqual(soma, pagamentos["total"])


class TestEventosGrupoStats(unittest.TestCase):
    """Testes para estatísticas de eventos de grupo ao longo do tempo (R8)"""

    def test_no_group_events(self):
        msgs = [_make_msg(body="Olá"), _make_msg(body="Tudo bem?")]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        eventos = stats.generate_all()["eventos_grupo"]
        self.assertEqual(eventos["total"], 0)
        self.assertEqual(eventos["por_periodo"], [])

    def test_group_events_from_subscription_event_and_users(self):
        msgs = [
            _make_msg(subscription_event="subscribe", sent=datetime(2024, 1, 10)),
            _make_msg(subscription_users=["userX"], sent=datetime(2024, 1, 15)),
            _make_msg(subscription_event="unsubscribe", sent=datetime(2024, 2, 1)),
            _make_msg(body="mensagem normal", sent=datetime(2024, 2, 2)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        eventos = stats.generate_all()["eventos_grupo"]

        self.assertEqual(eventos["total"], 3)
        self.assertEqual(
            eventos["por_periodo"],
            [
                {"periodo": "2024-01", "contagem": 2},
                {"periodo": "2024-02", "contagem": 1},
            ],
        )
        soma = sum(item["contagem"] for item in eventos["por_periodo"])
        self.assertEqual(soma, eventos["total"])


class TestRemovidasTemporalStats(unittest.TestCase):
    """Testes para estatísticas de mensagens removidas ao longo do tempo (R9)"""

    def test_no_removed_messages(self):
        msgs = [_make_msg(body="Olá"), _make_msg(body="Tudo bem?")]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        removidas = stats.generate_all()["removidas_temporal"]
        self.assertEqual(removidas["total"], 0)
        self.assertEqual(removidas["por_periodo"], [])

    def test_removed_messages_aggregated_by_period(self):
        msgs = [
            _make_msg(removed_by_sender=True, sent=datetime(2024, 1, 10)),
            _make_msg(removed_by_sender=True, sent=datetime(2024, 1, 20)),
            _make_msg(removed_by_sender=True, sent=datetime(2024, 3, 5)),
            _make_msg(removed_by_sender=False, sent=datetime(2024, 3, 6)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        removidas = stats.generate_all()["removidas_temporal"]

        self.assertEqual(removidas["total"], 3)
        # Ordenado cronologicamente
        self.assertEqual(
            removidas["por_periodo"],
            [
                {"periodo": "2024-01", "contagem": 2},
                {"periodo": "2024-03", "contagem": 1},
            ],
        )
        # Total iguala a soma das contagens por período
        soma = sum(item["contagem"] for item in removidas["por_periodo"])
        self.assertEqual(soma, removidas["total"])


class TestTemporariasTemporalStats(unittest.TestCase):
    """Testes para estatísticas de mensagens temporárias ao longo do tempo (R9)"""

    def test_no_disappearing_messages(self):
        msgs = [_make_msg(body="Olá"), _make_msg(body="Tudo bem?")]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        temporarias = stats.generate_all()["temporarias_temporal"]
        self.assertEqual(temporarias["total"], 0)
        self.assertEqual(temporarias["por_periodo"], [])

    def test_disappearing_messages_aggregated_by_period(self):
        msgs = [
            _make_msg(disappearing=True, sent=datetime(2024, 1, 10)),
            _make_msg(disappearing=True, sent=datetime(2024, 1, 20)),
            _make_msg(disappearing=True, sent=datetime(2024, 3, 5)),
            _make_msg(disappearing=False, sent=datetime(2024, 3, 6)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        temporarias = stats.generate_all()["temporarias_temporal"]

        self.assertEqual(temporarias["total"], 3)
        # Ordenado cronologicamente
        self.assertEqual(
            temporarias["por_periodo"],
            [
                {"periodo": "2024-01", "contagem": 2},
                {"periodo": "2024-03", "contagem": 1},
            ],
        )
        # Total iguala a soma das contagens por período
        soma = sum(item["contagem"] for item in temporarias["por_periodo"])
        self.assertEqual(soma, temporarias["total"])


class TestDominiosStats(unittest.TestCase):
    """Testes para estatísticas de domínios de links compartilhados (R10)"""

    def test_no_links(self):
        msgs = [_make_msg(body="Olá"), _make_msg(body="Tudo bem?")]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        dominios = stats.generate_all()["dominios"]
        self.assertEqual(dominios["total"], 0)
        self.assertEqual(dominios["por_dominio"], [])

    def test_aggregated_and_sorted_descending(self):
        msgs = [
            _make_msg(share_url="https://example.com/a"),
            _make_msg(share_url="https://example.com/b"),
            _make_msg(share_url="https://example.com/c"),
            _make_msg(share_url="https://news.com/x"),
            _make_msg(share_url="https://news.com/y"),
            _make_msg(share_url="https://blog.org/z"),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        dominios = stats.generate_all()["dominios"]

        self.assertEqual(dominios["total"], 6)
        # Ordenado por contagem decrescente
        self.assertEqual(
            dominios["por_dominio"],
            [
                {"dominio": "example.com", "contagem": 3},
                {"dominio": "news.com", "contagem": 2},
                {"dominio": "blog.org", "contagem": 1},
            ],
        )
        # Total iguala a soma das contagens por domínio
        soma = sum(item["contagem"] for item in dominios["por_dominio"])
        self.assertEqual(soma, dominios["total"])

    def test_host_extraction_ignores_port_and_case(self):
        # urlparse.hostname normaliza para minúsculas e remove a porta,
        # então variações do mesmo host são agregadas juntas.
        msgs = [
            _make_msg(share_url="https://Example.COM:8080/path?q=1"),
            _make_msg(share_url="http://example.com/outro"),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        dominios = stats.generate_all()["dominios"]

        self.assertEqual(dominios["total"], 2)
        self.assertEqual(
            dominios["por_dominio"],
            [{"dominio": "example.com", "contagem": 2}],
        )

    def test_invalid_urls_excluded_without_interrupting(self):
        # URLs sem host válido (sem esquema, vazias, ou apenas texto) são
        # excluídas sem interromper o cálculo das URLs válidas.
        msgs = [
            _make_msg(share_url="https://valid.com/post"),
            _make_msg(share_url="example.com/sem-esquema"),  # sem host (vai para path)
            _make_msg(share_url="not a url"),
            _make_msg(share_url=""),
            _make_msg(share_url=None),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        dominios = stats.generate_all()["dominios"]

        self.assertEqual(dominios["total"], 1)
        self.assertEqual(
            dominios["por_dominio"],
            [{"dominio": "valid.com", "contagem": 1}],
        )


class TestIniciativaStats(unittest.TestCase):
    """Testes para o indicador de iniciativa (inícios/encerramentos) (R11)"""

    def test_no_threads(self):
        # Conjunto vazio reporta totais e lista zerados sem erro.
        stats = ChatStatistics([])
        iniciativa = stats.generate_all()["iniciativa"]
        self.assertEqual(iniciativa["total_inicios"], 0)
        self.assertEqual(iniciativa["total_encerramentos"], 0)
        self.assertEqual(iniciativa["por_autor"], [])

    def test_single_session_first_start_last_end(self):
        # Sem gaps acima do limiar: uma única sessão. O primeiro autor recebe um
        # início e o autor da última mensagem recebe um encerramento.
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            _make_msg(author="user1", sent=base),
            _make_msg(author="user2", sent=base + timedelta(minutes=5)),
            _make_msg(author="user1", sent=base + timedelta(minutes=10)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        iniciativa = stats.generate_all()["iniciativa"]

        self.assertEqual(iniciativa["total_inicios"], 1)
        self.assertEqual(iniciativa["total_encerramentos"], 1)
        por_autor = {a["nome"]: a for a in iniciativa["por_autor"]}
        # user1 inicia (primeira msg) e encerra (última msg) a sessão única.
        self.assertEqual(por_autor["user1"]["inicios"], 1)
        self.assertEqual(por_autor["user1"]["encerramentos"], 1)
        # user2 apenas participa no meio: nem início nem encerramento.
        self.assertEqual(por_autor.get("user2", {"inicios": 0})["inicios"], 0)

    def test_gap_creates_new_session_with_attribution(self):
        # Um gap acima do limiar (30 min padrão) cria uma nova sessão: a mensagem
        # anterior encerra (R11.3) e a posterior inicia (R11.1, R11.2).
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            _make_msg(author="user1", sent=base),  # início sessão 1
            _make_msg(author="user2", sent=base + timedelta(minutes=5)),  # fim sessão 1
            # gap de 2h -> nova sessão
            _make_msg(author="user2", sent=base + timedelta(hours=2)),  # início sessão 2
            _make_msg(author="user1", sent=base + timedelta(hours=2, minutes=5)),  # fim sessão 2
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        iniciativa = stats.generate_all()["iniciativa"]

        self.assertEqual(iniciativa["total_inicios"], 2)
        self.assertEqual(iniciativa["total_encerramentos"], 2)
        por_autor = {a["nome"]: a for a in iniciativa["por_autor"]}
        # user1 inicia a sessão 1; user2 inicia a sessão 2
        self.assertEqual(por_autor["user1"]["inicios"], 1)
        self.assertEqual(por_autor["user2"]["inicios"], 1)
        # user2 encerra a sessão 1; user1 encerra a sessão 2
        self.assertEqual(por_autor["user2"]["encerramentos"], 1)
        self.assertEqual(por_autor["user1"]["encerramentos"], 1)

    def test_starts_equal_endings_and_sessions(self):
        # Propriedade-chave: nº de inícios == nº de encerramentos == nº de sessões.
        base = datetime(2024, 1, 1, 8, 0, 0)
        msgs = [
            _make_msg(author="user1", sent=base),
            _make_msg(author="user2", sent=base + timedelta(hours=3)),  # sessão 2
            _make_msg(author="user1", sent=base + timedelta(hours=6)),  # sessão 3
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        iniciativa = stats.generate_all()["iniciativa"]

        self.assertEqual(iniciativa["total_inicios"], 3)
        self.assertEqual(iniciativa["total_inicios"], iniciativa["total_encerramentos"])
        # Soma das contagens por autor iguala os totais
        soma_inicios = sum(a["inicios"] for a in iniciativa["por_autor"])
        soma_fins = sum(a["encerramentos"] for a in iniciativa["por_autor"])
        self.assertEqual(soma_inicios, iniciativa["total_inicios"])
        self.assertEqual(soma_fins, iniciativa["total_encerramentos"])

    def test_ignores_undated_messages(self):
        # Mensagens sem data (sent=None) não participam da delimitação de sessões.
        # Construímos as mensagens diretamente para preservar sent=None (o helper
        # _make_msg substitui None por uma data padrão).
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            Message(author="user1", author_id="100", platform="instagram", sent=base, body="oi"),
            Message(
                author="user2", author_id="200", platform="instagram", sent=None, body="sem data"
            ),
            Message(
                author="user1",
                author_id="100",
                platform="instagram",
                sent=base + timedelta(minutes=10),
                body="resposta",
            ),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        iniciativa = stats.generate_all()["iniciativa"]

        # Apenas duas mensagens datadas sem gap -> uma sessão.
        self.assertEqual(iniciativa["total_inicios"], 1)
        self.assertEqual(iniciativa["total_encerramentos"], 1)


class TestReciprocidadeStats(unittest.TestCase):
    """Testes para o índice de reciprocidade por DM (R12)"""

    def test_balanced_dm_index_near_one(self):
        # DM equilibrada: ambos enviam a mesma quantidade de mensagens e caracteres.
        msgs = [
            _make_msg(author="user1", body="abcde"),
            _make_msg(author="user2", body="fghij"),
            _make_msg(author="user1", body="klmno"),
            _make_msg(author="user2", body="pqrst"),
        ]
        thread = _make_thread(messages=msgs)
        reciprocidade = ChatStatistics([thread]).generate_all()["reciprocidade"]

        self.assertEqual(len(reciprocidade), 1)
        self.assertEqual(reciprocidade[0]["thread_id"], "1")
        self.assertEqual(reciprocidade[0]["indice_msgs"], 1.0)
        self.assertEqual(reciprocidade[0]["indice_chars"], 1.0)

    def test_one_sided_dm_index_near_zero(self):
        # DM fortemente unilateral: user1 envia muito, user2 quase nada.
        msgs = [_make_msg(author="user1", body="texto longo aqui") for _ in range(10)]
        msgs.append(_make_msg(author="user2", body="a"))
        thread = _make_thread(messages=msgs)
        reciprocidade = ChatStatistics([thread]).generate_all()["reciprocidade"]

        self.assertEqual(len(reciprocidade), 1)
        # 1 mensagem de user2 contra 10 de user1 -> 1/10 = 0.1
        self.assertAlmostEqual(reciprocidade[0]["indice_msgs"], 0.1, places=4)
        # 1 caractere contra 16*10 -> índice muito próximo de zero
        self.assertLess(reciprocidade[0]["indice_chars"], 0.05)
        # Os índices permanecem no intervalo [0, 1].
        self.assertGreaterEqual(reciprocidade[0]["indice_msgs"], 0.0)
        self.assertLessEqual(reciprocidade[0]["indice_msgs"], 1.0)

    def test_group_excluded(self):
        # Conversa de grupo (3 participantes) é excluída do cálculo (R12.4).
        participants = [
            Participant("user1", "instagram", "100"),
            Participant("user2", "instagram", "200"),
            Participant("user3", "instagram", "300"),
        ]
        msgs = [
            _make_msg(author="user1"),
            _make_msg(author="user2"),
            _make_msg(author="user3"),
        ]
        thread = _make_thread(participants=participants, messages=msgs)
        reciprocidade = ChatStatistics([thread]).generate_all()["reciprocidade"]

        self.assertEqual(reciprocidade, [])

    def test_empty_dm_index_one(self):
        # DM sem mensagens: ambos os lados zero -> índice 1.0 (vacuamente equilibrado).
        thread = _make_thread(messages=[])
        reciprocidade = ChatStatistics([thread]).generate_all()["reciprocidade"]

        self.assertEqual(len(reciprocidade), 1)
        self.assertEqual(reciprocidade[0]["indice_msgs"], 1.0)
        self.assertEqual(reciprocidade[0]["indice_chars"], 1.0)


class TestSessoesStats(unittest.TestCase):
    """Testes para estatísticas de sessões de conversa (R13)"""

    def test_no_threads(self):
        # Conjunto vazio reporta lista vazia sem erro.
        sessoes = ChatStatistics([]).generate_all()["sessoes"]
        self.assertEqual(sessoes, [])

    def test_single_message_one_session_zero_duration(self):
        # Conversa com uma única mensagem: uma sessão com duração zero (R13.3, R13.4).
        msgs = [_make_msg(author="user1", sent=datetime(2024, 1, 1, 10, 0, 0))]
        thread = _make_thread(messages=msgs)
        sessoes = ChatStatistics([thread]).generate_all()["sessoes"]

        self.assertEqual(len(sessoes), 1)
        self.assertEqual(sessoes[0]["thread_id"], "1")
        self.assertEqual(sessoes[0]["num_sessoes"], 1)
        self.assertEqual(sessoes[0]["duracao_media_segundos"], 0.0)

    def test_single_session_no_gap(self):
        # Sem gaps acima do limiar: uma única sessão. Duração = última - primeira.
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            _make_msg(author="user1", sent=base),
            _make_msg(author="user2", sent=base + timedelta(minutes=5)),
            _make_msg(author="user1", sent=base + timedelta(minutes=20)),
        ]
        thread = _make_thread(messages=msgs)
        sessoes = ChatStatistics([thread]).generate_all()["sessoes"]

        self.assertEqual(len(sessoes), 1)
        self.assertEqual(sessoes[0]["num_sessoes"], 1)
        # Duração da única sessão = 20 min = 1200 s.
        self.assertEqual(sessoes[0]["duracao_media_segundos"], 1200.0)

    def test_gap_splits_into_two_sessions(self):
        # Um gap acima do limiar (30 min padrão) cria uma segunda sessão (R13.1).
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            _make_msg(author="user1", sent=base),  # sessão 1 início
            _make_msg(author="user2", sent=base + timedelta(minutes=10)),  # sessão 1 fim
            # gap de 2h -> nova sessão
            _make_msg(author="user1", sent=base + timedelta(hours=2)),  # sessão 2 início
            _make_msg(author="user2", sent=base + timedelta(hours=2, minutes=30)),  # sessão 2 fim
        ]
        thread = _make_thread(messages=msgs)
        sessoes = ChatStatistics([thread]).generate_all()["sessoes"]

        self.assertEqual(len(sessoes), 1)
        self.assertEqual(sessoes[0]["num_sessoes"], 2)
        # Sessão 1: 10 min = 600 s; Sessão 2: 30 min = 1800 s; média = 1200 s.
        self.assertEqual(sessoes[0]["duracao_media_segundos"], 1200.0)

    def test_message_count_conserved_across_sessions(self):
        # Propriedade 12: a soma das mensagens entre as sessões iguala o total de
        # mensagens datadas da conversa. Aqui validamos indiretamente que cada
        # mensagem é atribuída a exatamente uma sessão contando os limites de gap.
        base = datetime(2024, 1, 1, 8, 0, 0)
        msgs = [
            _make_msg(author="user1", sent=base),
            _make_msg(author="user2", sent=base + timedelta(hours=3)),  # gap -> sessão 2
            _make_msg(author="user1", sent=base + timedelta(hours=3, minutes=10)),
            _make_msg(author="user2", sent=base + timedelta(hours=6)),  # gap -> sessão 3
        ]
        thread = _make_thread(messages=msgs)
        sessoes = ChatStatistics([thread]).generate_all()["sessoes"]

        self.assertEqual(len(sessoes), 1)
        # Três sessões delimitadas por dois gaps acima do limiar.
        self.assertEqual(sessoes[0]["num_sessoes"], 3)

    def test_ignores_undated_messages(self):
        # Mensagens sem data (sent=None) não participam da delimitação de sessões.
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            Message(author="user1", author_id="100", platform="instagram", sent=base, body="oi"),
            Message(
                author="user2", author_id="200", platform="instagram", sent=None, body="sem data"
            ),
            Message(
                author="user1",
                author_id="100",
                platform="instagram",
                sent=base + timedelta(minutes=10),
                body="resposta",
            ),
        ]
        thread = _make_thread(messages=msgs)
        sessoes = ChatStatistics([thread]).generate_all()["sessoes"]

        # Apenas duas mensagens datadas sem gap -> uma sessão de 10 min.
        self.assertEqual(len(sessoes), 1)
        self.assertEqual(sessoes[0]["num_sessoes"], 1)
        self.assertEqual(sessoes[0]["duracao_media_segundos"], 600.0)


class TestEsfriamentoStats(unittest.TestCase):
    """Testes para a evolução do contato e detecção de esfriamento (R14)"""

    @staticmethod
    def _msgs_periodos(volumes_por_mes):
        """Gera mensagens datadas de modo que cada mês (a partir de 2024-01)
        receba a quantidade indicada em ``volumes_por_mes``."""
        msgs = []
        for idx, total in enumerate(volumes_por_mes):
            mes = idx + 1
            for _ in range(total):
                msgs.append(_make_msg(sent=datetime(2024, mes, 15, 10, 0, 0)))
        return msgs

    def test_no_threads(self):
        # Conjunto vazio reporta lista vazia sem erro.
        esfriamento = ChatStatistics([]).generate_all()["esfriamento"]
        self.assertEqual(esfriamento, [])

    def test_no_dated_messages(self):
        # Sem mensagens datadas: série vazia e não sinalizada.
        msgs = [
            Message(
                author="user1", author_id="100", platform="instagram", sent=None, body="sem data"
            )
        ]
        thread = _make_thread(messages=msgs)
        esfriamento = ChatStatistics([thread]).generate_all()["esfriamento"]
        self.assertEqual(len(esfriamento), 1)
        self.assertEqual(esfriamento[0]["serie_temporal"], [])
        self.assertFalse(esfriamento[0]["em_esfriamento"])

    def test_monotonic_decreasing_is_cooling(self):
        # Série monotonicamente decrescente além do limiar (queda de 100% > 0.5).
        msgs = self._msgs_periodos([10, 6, 3, 1])
        thread = _make_thread(messages=msgs)
        esfriamento = ChatStatistics([thread]).generate_all()["esfriamento"]

        serie = esfriamento[0]["serie_temporal"]
        # A série é exposta em ordem cronológica (R14.3).
        self.assertEqual(
            serie,
            [
                {"periodo": "2024-01", "total": 10},
                {"periodo": "2024-02", "total": 6},
                {"periodo": "2024-03", "total": 3},
                {"periodo": "2024-04", "total": 1},
            ],
        )
        self.assertTrue(esfriamento[0]["em_esfriamento"])

    def test_stable_is_not_cooling(self):
        # Série estável (volumes iguais): queda relativa zero, não sinalizada.
        msgs = self._msgs_periodos([5, 5, 5, 5])
        thread = _make_thread(messages=msgs)
        esfriamento = ChatStatistics([thread]).generate_all()["esfriamento"]
        self.assertFalse(esfriamento[0]["em_esfriamento"])

    def test_increasing_is_not_cooling(self):
        # Série crescente: viola a monotonicidade não-crescente.
        msgs = self._msgs_periodos([1, 3, 6, 10])
        thread = _make_thread(messages=msgs)
        esfriamento = ChatStatistics([thread]).generate_all()["esfriamento"]
        self.assertFalse(esfriamento[0]["em_esfriamento"])

    def test_decreasing_below_threshold_is_not_cooling(self):
        # Queda sustentada porém pequena (10 -> 9 = 10% < 50%): não sinalizada.
        msgs = self._msgs_periodos([10, 9])
        thread = _make_thread(messages=msgs)
        esfriamento = ChatStatistics([thread]).generate_all()["esfriamento"]
        self.assertFalse(esfriamento[0]["em_esfriamento"])

    def test_non_monotonic_drop_is_not_cooling(self):
        # Queda total grande, mas com repique no meio: não é queda sustentada.
        msgs = self._msgs_periodos([10, 2, 8, 1])
        thread = _make_thread(messages=msgs)
        esfriamento = ChatStatistics([thread]).generate_all()["esfriamento"]
        self.assertFalse(esfriamento[0]["em_esfriamento"])

    def test_single_period_is_not_cooling(self):
        # Um único período não permite avaliar tendência.
        msgs = self._msgs_periodos([7])
        thread = _make_thread(messages=msgs)
        esfriamento = ChatStatistics([thread]).generate_all()["esfriamento"]
        self.assertEqual(len(esfriamento[0]["serie_temporal"]), 1)
        self.assertFalse(esfriamento[0]["em_esfriamento"])


class TestStreaksStats(unittest.TestCase):
    """Testes para os streaks de dias consecutivos (R15)"""

    def test_no_threads(self):
        # Conjunto vazio reporta lista vazia sem erro.
        streaks = ChatStatistics([]).generate_all()["streaks"]
        self.assertEqual(streaks, [])

    def test_no_dated_messages_zero_streak(self):
        # Sem mensagens datadas: streak zero e intervalo vazio (R15.3).
        msgs = [
            Message(
                author="user1", author_id="100", platform="instagram", sent=None, body="sem data"
            )
        ]
        thread = _make_thread(messages=msgs)
        streaks = ChatStatistics([thread]).generate_all()["streaks"]

        self.assertEqual(len(streaks), 1)
        self.assertEqual(streaks[0]["thread_id"], "1")
        self.assertEqual(streaks[0]["maior_streak_dias"], 0)
        self.assertEqual(streaks[0]["inicio"], "")
        self.assertEqual(streaks[0]["fim"], "")

    def test_single_day_streak_one(self):
        # Uma única data (mesmo com várias mensagens): streak de comprimento 1.
        msgs = [
            _make_msg(sent=datetime(2024, 1, 10, 9, 0, 0)),
            _make_msg(sent=datetime(2024, 1, 10, 18, 0, 0)),
        ]
        thread = _make_thread(messages=msgs)
        streaks = ChatStatistics([thread]).generate_all()["streaks"]

        self.assertEqual(streaks[0]["maior_streak_dias"], 1)
        self.assertEqual(streaks[0]["inicio"], "2024-01-10")
        self.assertEqual(streaks[0]["fim"], "2024-01-10")

    def test_consecutive_days_streak(self):
        # Três dias consecutivos formam um streak de comprimento 3 (R15.1, R15.2).
        msgs = [
            _make_msg(sent=datetime(2024, 1, 1, 10, 0, 0)),
            _make_msg(sent=datetime(2024, 1, 2, 10, 0, 0)),
            _make_msg(sent=datetime(2024, 1, 3, 10, 0, 0)),
        ]
        thread = _make_thread(messages=msgs)
        streaks = ChatStatistics([thread]).generate_all()["streaks"]

        self.assertEqual(streaks[0]["maior_streak_dias"], 3)
        self.assertEqual(streaks[0]["inicio"], "2024-01-01")
        self.assertEqual(streaks[0]["fim"], "2024-01-03")

    def test_longest_among_multiple_runs(self):
        # Várias sequências separadas por lacunas: reporta a maior delas.
        # Run A: 01,02 (2 dias). Run B: 10,11,12,13 (4 dias). Run C: 20 (1 dia).
        dias = [1, 2, 10, 11, 12, 13, 20]
        msgs = [_make_msg(sent=datetime(2024, 1, d, 10, 0, 0)) for d in dias]
        thread = _make_thread(messages=msgs)
        streaks = ChatStatistics([thread]).generate_all()["streaks"]

        self.assertEqual(streaks[0]["maior_streak_dias"], 4)
        self.assertEqual(streaks[0]["inicio"], "2024-01-10")
        self.assertEqual(streaks[0]["fim"], "2024-01-13")

    def test_streak_length_matches_interval(self):
        # Propriedade 14: comprimento == (fim - inicio em dias) + 1.
        msgs = [_make_msg(sent=datetime(2024, 2, d, 10, 0, 0)) for d in range(5, 11)]
        thread = _make_thread(messages=msgs)
        info = ChatStatistics([thread]).generate_all()["streaks"][0]

        inicio = datetime.strptime(info["inicio"], "%Y-%m-%d")
        fim = datetime.strptime(info["fim"], "%Y-%m-%d")
        self.assertEqual(info["maior_streak_dias"], (fim - inicio).days + 1)

    def test_ignores_undated_messages(self):
        # Mensagens sem data não afetam o cálculo do streak.
        msgs = [
            _make_msg(sent=datetime(2024, 1, 1, 10, 0, 0)),
            Message(
                author="user2", author_id="200", platform="instagram", sent=None, body="sem data"
            ),
            _make_msg(sent=datetime(2024, 1, 2, 10, 0, 0)),
        ]
        thread = _make_thread(messages=msgs)
        streaks = ChatStatistics([thread]).generate_all()["streaks"]

        self.assertEqual(streaks[0]["maior_streak_dias"], 2)
        self.assertEqual(streaks[0]["inicio"], "2024-01-01")
        self.assertEqual(streaks[0]["fim"], "2024-01-02")


class TestGenerateAll(unittest.TestCase):
    """Testes para generate_all() - verifica todas as chaves retornadas"""

    def test_all_keys_present(self):
        msgs = [_make_msg()]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread])
        result = stats.generate_all()

        expected_keys = [
            "resumo",
            "por_participante",
            "por_conversa",
            "temporal",
            "midias",
            "chamadas",
            "palavras",
            "horarios",
            "top_conversas",
            "tempo_resposta",
            "heatmap",
            "reacoes",
            "emojis",
            "integridade_anexos",
            "gaps",
            "grafo",
            "tamanho_msgs",
            "comparacao_periodos",
            "idiomas",
            "iniciativa",
            "reciprocidade",
            "sessoes",
            "esfriamento",
            "streaks",
        ]
        for key in expected_keys:
            self.assertIn(key, result, f"Chave '{key}' ausente em generate_all()")


# Feature: melhorias-analise-e-projeto, Property 6: Mediana do tempo de resposta é correta
@settings(max_examples=200)
@given(gaps=st.lists(st.integers(min_value=1, max_value=86400), min_size=3, max_size=15))
def test_property_mediana_tempo_resposta_correta(gaps):
    """Para qualquer conjunto não vazio de tempos de resposta, a mediana reportada deve
    ser igual a statistics.median do conjunto (média dos dois centrais quando o tamanho
    é par, elemento central quando ímpar).

    Constrói uma DM (dois participantes) alternando B -> A com intervalos conhecidos
    (cada `gap` em segundos, dentro do limite de 24h, atribuído a "userA"). As respostas
    de A -> B usam um intervalo grande (> 24h), filtrado pela engine, garantindo que o
    conjunto de tempos de resposta de "userA" seja exatamente `gaps`.

    Validates: Requirements 6.1, 6.2, 6.3
    """
    base = datetime(2024, 1, 1, 0, 0, 0)
    big_gap = 90_000  # > 86400s (24h): a engine descarta esses deltas A -> B

    msgs = [Message(author="userB", author_id="200", platform="instagram", sent=base, body="oi")]
    offset = 0
    for gap in gaps:
        offset += gap
        # B -> A: delta == gap (<= 24h) -> registrado para userA
        msgs.append(
            Message(
                author="userA",
                author_id="100",
                platform="instagram",
                sent=base + timedelta(seconds=offset),
                body="resposta",
            )
        )
        offset += big_gap
        # A -> B: delta == big_gap (> 24h) -> descartado pela engine
        msgs.append(
            Message(
                author="userB",
                author_id="200",
                platform="instagram",
                sent=base + timedelta(seconds=offset),
                body="msg",
            )
        )

    thread = Thread(
        thread_id="1",
        thread_name="DM",
        participants=[
            Participant("userA", "instagram", "100"),
            Participant("userB", "instagram", "200"),
        ],
        messages=msgs,
    )

    stats = ChatStatistics([thread], "userA", "100")
    tempo_resposta = stats.generate_all()["tempo_resposta"]

    userA = next(item for item in tempo_resposta if item["nome"] == "userA")
    esperado = round(statistics.median(gaps))
    assert userA["mediana_segundos"] == esperado
    assert userA["total_respostas"] == len(gaps)


# Feature: melhorias-analise-e-projeto, Property 7: Estatísticas de mensagens editadas são conservadas
@settings(max_examples=200)
@given(msgs=st.lists(messages(), max_size=25))
def test_property_editadas_conservadas(msgs):
    """Para qualquer conjunto de mensagens, o total de editadas deve igualar a contagem de
    mensagens com `is_edited` verdadeiro; a soma das contagens por autor deve igualar o total;
    a lista de autores deve estar ordenada por contagem em ordem decrescente; e um conjunto
    sem editadas deve reportar total zero sem erro.

    Validates: Requirements 7.1, 7.2, 7.3, 7.4
    """
    thread = Thread(
        thread_id="1",
        thread_name="DM",
        participants=[
            Participant("userA", "instagram", "100"),
            Participant("userB", "instagram", "200"),
        ],
        messages=msgs,
    )

    stats = ChatStatistics([thread], "userA", "100")
    editadas = stats.generate_all()["editadas"]

    # R7.1: total == contagem de mensagens com is_edited verdadeiro.
    esperado_total = sum(1 for m in msgs if m.is_edited)
    assert editadas["total"] == esperado_total

    por_autor = editadas["por_autor"]

    # R7.2: a soma das contagens por autor iguala o total reportado.
    assert sum(item["total"] for item in por_autor) == editadas["total"]

    # R7.3: autores ordenados por contagem em ordem decrescente.
    totais = [item["total"] for item in por_autor]
    assert totais == sorted(totais, reverse=True)

    # Contagens por autor coincidem com a contagem direta a partir das mensagens.
    esperado_por_autor: dict[str, int] = {}
    for m in msgs:
        if m.is_edited:
            esperado_por_autor[m.author] = esperado_por_autor.get(m.author, 0) + 1
    assert {item["nome"]: item["total"] for item in por_autor} == esperado_por_autor

    # R7.4: conjunto sem editadas reporta total zero (lista vazia) sem erro.
    if esperado_total == 0:
        assert editadas["total"] == 0
        assert por_autor == []


# Feature: melhorias-analise-e-projeto, Property 8: Agregações temporais conservam os totais
@settings(max_examples=200)
@given(msgs=st.lists(messages(), max_size=25))
def test_property_agregacoes_temporais_conservam_totais(msgs):
    """Para qualquer conjunto de mensagens e para cada atributo agregado por período
    (`has_payment`, `subscription_event`/`subscription_users`, `removed_by_sender`,
    `disappearing`), a soma das contagens em todos os períodos deve igualar o total
    reportado para aquele atributo, e um conjunto sem ocorrências deve reportar total
    zero sem erro.

    Como a engine agrega apenas mensagens DATADAS (`sent` não nulo), o total esperado
    é a contagem de mensagens datadas com o atributo verdadeiro. O conjunto vazio é
    coberto explicitamente ao final.

    Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4
    """
    thread = Thread(
        thread_id="1",
        thread_name="DM",
        participants=[
            Participant("userA", "instagram", "100"),
            Participant("userB", "instagram", "200"),
        ],
        messages=msgs,
    )

    stats = ChatStatistics([thread], "userA", "100")
    result = stats.generate_all()

    # Cada família: (chave, predicado de "atributo verdadeiro" na mensagem).
    familias = {
        "pagamentos": lambda m: m.has_payment,
        "eventos_grupo": lambda m: bool(m.subscription_event or m.subscription_users),
        "removidas_temporal": lambda m: m.removed_by_sender,
        "temporarias_temporal": lambda m: m.disappearing,
    }

    for chave, predicado in familias.items():
        agregado = result[chave]
        por_periodo = agregado["por_periodo"]

        # Conservação: total == soma das contagens por período.
        soma = sum(item["contagem"] for item in por_periodo)
        assert agregado["total"] == soma, chave

        # A engine conta apenas mensagens datadas com o atributo verdadeiro.
        esperado = sum(1 for m in msgs if predicado(m) and m.sent)
        assert agregado["total"] == esperado, chave

    # Conjunto vazio: total zero e lista vazia, sem erro.
    empty_thread = Thread(
        thread_id="1",
        thread_name="DM",
        participants=[],
        messages=[],
    )
    empty_result = ChatStatistics([empty_thread], "userA", "100").generate_all()
    for chave in familias:
        assert empty_result[chave]["total"] == 0
        assert empty_result[chave]["por_periodo"] == []


# Estratégias de URL para a Property 9: mistura de URLs válidas e inválidas.
# URLs válidas têm esquema http(s) e host; inválidas não produzem host via urlparse.
_valid_share_url = st.builds(
    lambda scheme, host, port, path: f"{scheme}://{host}{port}{path}",
    scheme=st.sampled_from(["http", "https"]),
    host=st.sampled_from(
        ["example.com", "test.org", "sub.dominio.net", "GitHub.com", "a.io", "meta.com"]
    ),
    port=st.sampled_from(["", ":8080", ":443"]),
    path=st.sampled_from(["", "/", "/page", "/a/b?c=1", "/x#frag"]),
)
_invalid_share_url = st.sampled_from(
    ["", "   ", "texto qualquer", "sem-esquema", "www.semscheme.com", "/relativo/path", "12345678"]
)
_share_url_strategy = st.one_of(st.none(), _valid_share_url, _invalid_share_url)


# Feature: melhorias-analise-e-projeto, Property 9: Agregação de domínios é completa e ordenada
@settings(max_examples=200)
@given(urls=st.lists(_share_url_strategy, max_size=30))
def test_property_dominios_completa_e_ordenada(urls):
    """Para qualquer conjunto de mensagens, a soma das contagens por domínio deve igualar o
    número de mensagens cujo `share_url` possui host válido; os domínios devem estar ordenados
    por contagem em ordem decrescente; e URLs sem domínio válido devem ser excluídas sem
    interromper o cálculo.

    O esperado é computado espelhando a implementação (`urllib.parse.urlparse(...).hostname`).

    Validates: Requirements 10.1, 10.2, 10.3, 10.4
    """
    msgs = [_make_msg(share_url=u) for u in urls]
    thread = _make_thread(messages=msgs)

    stats = ChatStatistics([thread], "user1", "100")
    dominios = stats.generate_all()["dominios"]
    por_dominio = dominios["por_dominio"]

    # Espelha a implementação: extrai o host com urlparse, excluindo URLs sem host válido.
    esperado: Counter[str] = Counter()
    msgs_com_host_valido = 0
    for u in urls:
        if not u:
            continue
        try:
            host = urlparse(u).hostname
        except ValueError:
            continue
        if not host:
            continue
        esperado[host] += 1
        msgs_com_host_valido += 1

    # R10.1/R10.2/R10.4: total == nº de mensagens com host válido (URLs inválidas excluídas).
    assert dominios["total"] == msgs_com_host_valido

    # Completude: a soma das contagens por domínio iguala o total.
    assert sum(item["contagem"] for item in por_dominio) == dominios["total"]

    # R10.3: domínios ordenados por contagem em ordem decrescente.
    contagens = [item["contagem"] for item in por_dominio]
    assert contagens == sorted(contagens, reverse=True)

    # Agregação por domínio coincide com o cálculo de referência (inválidas excluídas).
    assert {item["dominio"]: item["contagem"] for item in por_dominio} == dict(esperado)


if __name__ == "__main__":
    unittest.main()


# Estratégia para a Property 10: um "passo" de conversa é um par
# (autor, minutos_desde_a_mensagem_anterior). Os autores vêm de um pequeno
# conjunto de participantes presentes; os intervalos cruzam o limiar de gap
# (30 min padrão) para produzir tanto continuações quanto novas sessões.
_INICIATIVA_AUTORES = ["ana", "bruno", "carla", "diego"]
_iniciativa_passo = st.tuples(
    st.sampled_from(_INICIATIVA_AUTORES),
    st.integers(min_value=0, max_value=180),
)


# Feature: melhorias-analise-e-projeto, Property 10: Iniciativa atribui inícios e encerramentos consistentes
@settings(max_examples=200)
@given(passos=st.lists(_iniciativa_passo, max_size=30))
def test_property_iniciativa_consistente(passos):
    """Para qualquer conversa, o número total de inícios de conversa deve igualar o número
    de sessões (determinado pelo limiar de gap), o número de encerramentos deve igualar o
    número de inícios, e cada início e encerramento deve ser atribuído a um autor presente
    na conversa.

    Constrói uma thread de mensagens datadas a partir de passos (autor, minutos desde a
    mensagem anterior), gerando timestamps cumulativos com intervalos variados. O número
    esperado de sessões é computado independentemente replicando a lógica do limiar de gap:
    ordenar as mensagens datadas, contar a primeira e cada intervalo > limiar.

    Validates: Requirements 11.1, 11.2, 11.3, 11.4
    """
    # Espelha o limiar usado pela engine (config.session_gap_minutes).
    from meta_chat_exporter.config import config as _cfg

    gap_threshold = timedelta(minutes=_cfg.session_gap_minutes)

    base = datetime(2024, 1, 1, 0, 0, 0)
    offset = timedelta()
    msgs = []
    autores_presentes = set()
    for autor, minutos in passos:
        offset += timedelta(minutes=minutos)
        msgs.append(_make_msg(author=autor, sent=base + offset))
        autores_presentes.add(autor)

    thread = _make_thread(messages=msgs)
    stats = ChatStatistics([thread], "ana", "100")
    iniciativa = stats.generate_all()["iniciativa"]

    # Número esperado de sessões: primeira mensagem datada + cada gap > limiar.
    dated = sorted((m for m in msgs if m.sent), key=lambda m: m.sent)
    if not dated:
        esperado_sessoes = 0
    else:
        esperado_sessoes = 1
        for i in range(1, len(dated)):
            if dated[i].sent - dated[i - 1].sent > gap_threshold:
                esperado_sessoes += 1

    # R11.1: total de inícios == número de sessões determinado pelo limiar de gap.
    assert iniciativa["total_inicios"] == esperado_sessoes

    # R11.3: número de encerramentos == número de inícios (uma sessão = 1 início + 1 fim).
    assert iniciativa["total_encerramentos"] == iniciativa["total_inicios"]

    # R11.2/R11.4: soma das contagens por autor iguala os totais reportados.
    soma_inicios = sum(item["inicios"] for item in iniciativa["por_autor"])
    soma_fins = sum(item["encerramentos"] for item in iniciativa["por_autor"])
    assert soma_inicios == iniciativa["total_inicios"]
    assert soma_fins == iniciativa["total_encerramentos"]

    # R11.2/R11.3: todo autor com início ou encerramento está presente na conversa.
    for item in iniciativa["por_autor"]:
        assert item["nome"] in autores_presentes


# Estratégia para a Property 11: um descritor de thread combina o número de
# participantes (2 = DM; 3+ = grupo, excluído) com uma lista de mensagens, cada
# uma autorada por um dos participantes da própria thread. Gerar uma mistura de
# DMs e grupos garante que o cálculo fique restrito às DMs (R12.4).
@st.composite
def _recip_thread_spec(draw):
    n_participants = draw(st.integers(min_value=2, max_value=5))
    msg_specs = draw(
        st.lists(
            st.tuples(st.integers(min_value=0, max_value=n_participants - 1), st.text(max_size=20)),
            max_size=8,
        )
    )
    return n_participants, msg_specs


# Feature: melhorias-analise-e-projeto, Property 11: Índice de reciprocidade é limitado e restrito a DMs
@settings(max_examples=200)
@given(specs=st.lists(_recip_thread_spec(), max_size=6))
def test_property_reciprocidade_limitada_e_restrita_a_dms(specs):
    """Para qualquer DM, os índices de reciprocidade de mensagens e de caracteres devem estar
    no intervalo [0, 1], valendo 1 quando há equilíbrio perfeito entre os dois participantes;
    conversas que não são DMs (grupos com 3+ participantes) devem ser excluídas do cálculo.

    Constrói uma mistura de DMs (2 participantes) e grupos (3+ participantes), com mensagens
    autoradas pelos próprios participantes de cada thread, e adiciona uma DM perfeitamente
    equilibrada de controle (ambos os lados com a mesma quantidade de mensagens e caracteres).

    Validates: Requirements 12.1, 12.2, 12.3, 12.4
    """
    threads = []
    dm_ids = set()
    for i, (n_participants, msg_specs) in enumerate(specs):
        tid = f"t{i}"
        participants = [
            Participant(f"{tid}_p{j}", "instagram", str(j)) for j in range(n_participants)
        ]
        nomes = [p[0] for p in participants]
        msgs = [_make_msg(author=nomes[idx], body=body) for idx, body in msg_specs]
        threads.append(
            Thread(thread_id=tid, thread_name="x", participants=participants, messages=msgs)
        )
        # DM == exatamente dois participantes (R12.4); grupos são excluídos.
        if n_participants == 2:
            dm_ids.add(tid)

    # DM de controle perfeitamente equilibrada: 2 msgs de 5 chars de cada lado.
    balanced_id = "balanced"
    balanced_participants = [
        Participant("bal_a", "instagram", "1"),
        Participant("bal_b", "instagram", "2"),
    ]
    balanced_msgs = [
        _make_msg(author="bal_a", body="abcde"),
        _make_msg(author="bal_b", body="vwxyz"),
        _make_msg(author="bal_a", body="12345"),
        _make_msg(author="bal_b", body="67890"),
    ]
    threads.append(
        Thread(
            thread_id=balanced_id,
            thread_name="bal",
            participants=balanced_participants,
            messages=balanced_msgs,
        )
    )
    dm_ids.add(balanced_id)

    reciprocidade = ChatStatistics(threads).generate_all()["reciprocidade"]
    result_ids = {item["thread_id"] for item in reciprocidade}

    # R12.4: apenas thread_ids de DMs aparecem; grupos (3+ participantes) são excluídos.
    assert result_ids == dm_ids

    # R12.1/R12.2/R12.3: cada índice (mensagens e caracteres) está no intervalo [0, 1].
    for item in reciprocidade:
        assert 0.0 <= item["indice_msgs"] <= 1.0
        assert 0.0 <= item["indice_chars"] <= 1.0

    # R12.3: a DM perfeitamente equilibrada tem índice 1.0 em ambos os eixos.
    balanced = next(item for item in reciprocidade if item["thread_id"] == balanced_id)
    assert balanced["indice_msgs"] == 1.0
    assert balanced["indice_chars"] == 1.0


# Estratégia para a Property 12: um "passo" de conversa é um par
# (autor, minutos_desde_a_mensagem_anterior), espelhando o padrão usado em
# test_property_iniciativa_consistente. Os intervalos cruzam o limiar de gap
# (30 min padrão) para produzir tanto continuações quanto novas sessões.
_SESSOES_AUTORES = ["ana", "bruno", "carla", "diego"]
_sessoes_passo = st.tuples(
    st.sampled_from(_SESSOES_AUTORES),
    st.integers(min_value=0, max_value=180),
)


# Feature: melhorias-analise-e-projeto, Property 12: Sessões particionam as mensagens da conversa
@settings(max_examples=200)
@given(passos=st.lists(_sessoes_passo, max_size=30))
def test_property_sessoes_particionam_mensagens(passos):
    """Para qualquer conversa, a soma do número de mensagens em todas as sessões (formadas
    pelo limiar de gap) deve igualar o total de mensagens datadas da conversa; uma conversa
    com uma única mensagem deve reportar exatamente uma sessão com duração zero.

    Constrói uma thread de mensagens datadas a partir de passos (autor, minutos desde a
    mensagem anterior), gerando timestamps cumulativos com intervalos variados. O número
    esperado de sessões é computado independentemente replicando a lógica do limiar de gap:
    ordenar as mensagens datadas e contar a primeira mais cada intervalo > limiar.

    Validates: Requirements 13.1, 13.2, 13.3, 13.4
    """
    # Espelha o limiar usado pela engine (config.session_gap_minutes).
    from meta_chat_exporter.config import config as _cfg

    gap_threshold = timedelta(minutes=_cfg.session_gap_minutes)

    base = datetime(2024, 1, 1, 0, 0, 0)
    offset = timedelta()
    msgs = []
    for autor, minutos in passos:
        offset += timedelta(minutes=minutos)
        msgs.append(_make_msg(author=autor, sent=base + offset))

    thread = _make_thread(messages=msgs)
    sessoes = ChatStatistics([thread], "ana", "100").generate_all()["sessoes"]

    dated = sorted((m for m in msgs if m.sent), key=lambda m: m.sent)

    # Número esperado de sessões: primeira mensagem datada + cada gap > limiar.
    if not dated:
        esperado_sessoes = 0
    else:
        esperado_sessoes = 1
        for i in range(1, len(dated)):
            if dated[i].sent - dated[i - 1].sent > gap_threshold:
                esperado_sessoes += 1

    if not dated:
        # Conversa sem mensagens datadas não contribui para a saída.
        assert sessoes == []
        return

    assert len(sessoes) == 1
    info = sessoes[0]

    # R13.1/R13.2: o número de sessões reportado coincide com a partição
    # independente pelo limiar de gap.
    assert info["num_sessoes"] == esperado_sessoes

    # As sessões particionam as mensagens datadas: cada sessão tem ao menos uma
    # mensagem, logo 1 <= num_sessoes <= número de mensagens datadas. Como cada
    # mensagem pertence a exatamente uma sessão, a soma das mensagens entre as
    # sessões iguala o total de mensagens datadas (conservação).
    assert 1 <= info["num_sessoes"] <= len(dated)

    # R13.3/R13.4: uma conversa com uma única mensagem datada reporta exatamente
    # uma sessão com duração zero.
    if len(dated) == 1:
        assert info["num_sessoes"] == 1
        assert info["duracao_media_segundos"] == 0.0


# Estratégia para a Property 13: uma série de volumes mensais como lista de
# inteiros positivos. Hypothesis explora naturalmente séries decrescentes,
# estáveis, crescentes e mistas, cobrindo os três casos da propriedade. Permite
# lista vazia (conversa sem mensagens datadas) e listas de tamanho 1 (sem
# tendência a avaliar).
_esfriamento_volumes = st.lists(
    st.integers(min_value=1, max_value=50),
    min_size=0,
    max_size=24,
)


# Feature: melhorias-analise-e-projeto, Property 13: Volume sustentadamente decrescente é sinalizado como esfriamento
@settings(max_examples=200)
@given(volumes=_esfriamento_volumes)
def test_property_esfriamento_decrescente_sinalizado(volumes):
    """Para qualquer conversa cuja série temporal de volume é monotonicamente decrescente ao
    longo de períodos consecutivos além do limiar configurável, a conversa deve ser sinalizada
    como em esfriamento; séries estáveis ou crescentes não devem ser sinalizadas. A série
    temporal usada deve ser exposta.

    Constrói uma thread com ``volumes[i]`` mensagens em meses consecutivos distintos
    (índice de mês ``i`` -> ``datetime(2024 + i // 12, i % 12 + 1, 15)``), de modo que a série
    temporal mensal agregada pela engine reproduza exatamente ``volumes`` em ordem cronológica.
    O ``em_esfriamento`` esperado é computado independentemente, espelhando a regra de 3
    condições da engine (n >= 2, monotonicamente não-crescente e queda relativa total acima de
    ``config.cooling_threshold``).

    Validates: Requirements 14.1, 14.2, 14.3, 14.4
    """
    # Espelha o limiar usado pela engine (config.cooling_threshold).
    from meta_chat_exporter.config import config as _cfg

    limiar = _cfg.cooling_threshold

    # Constrói as mensagens: para cada período i, cria volumes[i] mensagens
    # datadas em um mês consecutivo distinto.
    msgs = []
    for i, total in enumerate(volumes):
        mes_dt = datetime(2024 + i // 12, i % 12 + 1, 15, 12, 0, 0)
        for _ in range(total):
            msgs.append(_make_msg(author="user1", sent=mes_dt))

    thread = _make_thread(messages=msgs)
    esfriamento = ChatStatistics([thread], "user1", "100").generate_all()["esfriamento"]

    assert len(esfriamento) == 1
    info = esfriamento[0]
    assert info["thread_id"] == "1"

    # R14.1/R14.3: a série temporal é exposta e seus totais correspondem aos
    # volumes de entrada, em ordem cronológica.
    serie_totais = [item["total"] for item in info["serie_temporal"]]
    assert serie_totais == volumes
    periodos = [item["periodo"] for item in info["serie_temporal"]]
    assert periodos == sorted(periodos)

    # R14.2/R14.4: computa o esperado espelhando a regra de 3 condições da engine.
    def _esperado_em_esfriamento(vols: list[int]) -> bool:
        # Condição 1: pelo menos dois períodos.
        if len(vols) < 2:
            return False
        primeiro = vols[0]
        # Queda relativa exige ponto de partida positivo (sempre > 0 aqui).
        if primeiro <= 0:
            return False
        # Condição 2: monotonicamente não-crescente.
        for j in range(1, len(vols)):
            if vols[j] > vols[j - 1]:
                return False
        # Condição 3: queda relativa total acima do limiar configurável.
        return (primeiro - vols[-1]) / primeiro > limiar

    esperado = _esperado_em_esfriamento(volumes)
    assert info["em_esfriamento"] == esperado

    # Reforço explícito dos três casos da propriedade:
    if len(volumes) >= 2 and len(set(volumes)) == 1:
        # Série estável -> nunca sinalizada (queda relativa zero).
        assert info["em_esfriamento"] is False
    if len(volumes) >= 2 and any(volumes[j] > volumes[j - 1] for j in range(1, len(volumes))):
        # Série com qualquer repique/crescimento -> não sinalizada.
        assert info["em_esfriamento"] is False


# Estratégia para a Property 14: um conjunto de deslocamentos (em dias) a partir
# de uma data base. Deslocamentos repetidos representam várias mensagens no mesmo
# dia (a engine deduplica por data). A lista pode ser vazia, modelando uma
# conversa sem mensagens datadas (caso de streak zero). Hypothesis explora
# naturalmente dias dispersos, blocos consecutivos e dias isolados.
_streak_offsets = st.lists(
    st.integers(min_value=0, max_value=2000),
    min_size=0,
    max_size=40,
)


# Feature: melhorias-analise-e-projeto, Property 14: Streak reflete a maior sequência de dias consecutivos
@settings(max_examples=200)
@given(offsets=_streak_offsets)
def test_property_streak_maior_sequencia_consecutiva(offsets):
    """Para qualquer conjunto de mensagens datadas de uma conversa, o comprimento do maior
    streak deve ser igual a (data_fim − data_inicio em dias + 1) do intervalo reportado e
    corresponder à maior sequência de dias consecutivos com pelo menos uma mensagem; uma
    conversa sem mensagens datadas deve reportar streak de comprimento zero.

    Constrói uma thread com uma mensagem por deslocamento (em dias) a partir de uma data base;
    deslocamentos repetidos colidem no mesmo dia (a engine deduplica por ``date()``). O maior
    streak esperado é computado independentemente sobre o conjunto de datas distintas ordenadas,
    contando a maior corrida de dias de calendário estritamente consecutivos.

    Validates: Requirements 15.1, 15.2, 15.3
    """
    base = datetime(2020, 1, 1, 12, 0, 0)
    msgs = [_make_msg(author="user1", sent=base + timedelta(days=o)) for o in offsets]

    thread = _make_thread(messages=msgs)
    streaks = ChatStatistics([thread], "user1", "100").generate_all()["streaks"]

    assert len(streaks) == 1
    info = streaks[0]
    assert info["thread_id"] == "1"

    # Cálculo independente da maior corrida de dias consecutivos sobre as datas
    # distintas (espelha a definição da propriedade, não a implementação).
    datas = sorted({(base + timedelta(days=o)).date() for o in offsets})
    if not datas:
        esperado = 0
    else:
        melhor = 1
        corrente = 1
        for i in range(1, len(datas)):
            if datas[i] - datas[i - 1] == timedelta(days=1):
                corrente += 1
            else:
                corrente = 1
            melhor = max(melhor, corrente)
        esperado = melhor

    # R15.1: o maior streak reportado iguala a maior corrida de dias consecutivos.
    assert info["maior_streak_dias"] == esperado

    if not datas:
        # R15.3: conversa sem mensagens datadas reporta streak zero e intervalo vazio.
        assert info["maior_streak_dias"] == 0
        assert info["inicio"] == ""
        assert info["fim"] == ""
    else:
        # R15.2: o intervalo reportado é coerente com o comprimento do streak,
        # isto é, (fim - inicio) em dias + 1 == maior_streak_dias.
        inicio = datetime.strptime(info["inicio"], "%Y-%m-%d").date()
        fim = datetime.strptime(info["fim"], "%Y-%m-%d").date()
        assert (fim - inicio).days + 1 == info["maior_streak_dias"]
        # O intervalo está contido no conjunto de datas observadas.
        assert inicio in datas
        assert fim in datas


class TestNgramasStats(unittest.TestCase):
    """Testes para bigramas e trigramas (R16)"""

    def test_no_messages_empty_lists(self):
        # Conjunto sem conteúdo reporta listas vazias sem erro.
        thread = _make_thread(messages=[])
        ngramas = ChatStatistics([thread]).generate_all()["ngramas"]
        self.assertEqual(ngramas["bigramas"], [])
        self.assertEqual(ngramas["trigramas"], [])

    def test_bigrams_and_trigrams_basic(self):
        # "gato preto casa" -> 2 bigramas e 1 trigrama (tokens não são stop words).
        msgs = [_make_msg(author="user1", body="gato preto casa")]
        thread = _make_thread(messages=msgs)
        ngramas = ChatStatistics([thread]).generate_all()["ngramas"]

        bigramas = {b["ngrama"]: b["contagem"] for b in ngramas["bigramas"]}
        trigramas = {t["ngrama"]: t["contagem"] for t in ngramas["trigramas"]}
        self.assertEqual(bigramas, {"gato preto": 1, "preto casa": 1})
        self.assertEqual(trigramas, {"gato preto casa": 1})

    def test_stop_words_excluded_from_formation(self):
        # "gato de casa": "de" é stop word e é removida; os tokens restantes
        # adjacentes formam o bigrama "gato casa" (R16.3).
        msgs = [_make_msg(author="user1", body="gato de casa")]
        thread = _make_thread(messages=msgs)
        ngramas = ChatStatistics([thread]).generate_all()["ngramas"]

        ngrams_texto = [b["ngrama"] for b in ngramas["bigramas"]]
        self.assertIn("gato casa", ngrams_texto)
        # Nenhum n-grama contém a stop word "de".
        for item in ngramas["bigramas"] + ngramas["trigramas"]:
            self.assertNotIn("de", item["ngrama"].split())

    def test_ordered_by_frequency_descending(self):
        # "gato preto" aparece 3x; "casa azul" aparece 1x.
        msgs = [
            _make_msg(author="user1", body="gato preto"),
            _make_msg(author="user1", body="gato preto"),
            _make_msg(author="user1", body="gato preto"),
            _make_msg(author="user1", body="casa azul"),
        ]
        thread = _make_thread(messages=msgs)
        ngramas = ChatStatistics([thread]).generate_all()["ngramas"]

        bigramas = ngramas["bigramas"]
        self.assertEqual(bigramas[0], {"ngrama": "gato preto", "contagem": 3})
        # Ordenação decrescente por contagem.
        contagens = [b["contagem"] for b in bigramas]
        self.assertEqual(contagens, sorted(contagens, reverse=True))

    def test_ngrams_do_not_span_across_messages(self):
        # Cada mensagem tem um único token: nenhum bigrama é formado entre
        # mensagens distintas.
        msgs = [
            _make_msg(author="user1", body="gato"),
            _make_msg(author="user1", body="preto"),
        ]
        thread = _make_thread(messages=msgs)
        ngramas = ChatStatistics([thread]).generate_all()["ngramas"]
        self.assertEqual(ngramas["bigramas"], [])
        self.assertEqual(ngramas["trigramas"], [])

    def test_ignores_calls_and_removed_messages(self):
        # Chamadas e mensagens removidas não contribuem (mesma regra de palavras).
        msgs = [
            _make_msg(author="user1", body="ligacao perdida", is_call=True),
            _make_msg(author="user1", body="texto removido", removed_by_sender=True),
            _make_msg(author="user1", body="gato preto"),
        ]
        thread = _make_thread(messages=msgs)
        ngramas = ChatStatistics([thread]).generate_all()["ngramas"]
        bigramas = {b["ngrama"] for b in ngramas["bigramas"]}
        self.assertEqual(bigramas, {"gato preto"})

    def test_limit_top_n(self):
        # O limite restringe a quantidade de n-gramas retornados por tipo.
        msgs = [_make_msg(author="user1", body=f"palavra{i} valor{i}") for i in range(40)]
        thread = _make_thread(messages=msgs)
        ngramas = ChatStatistics([thread]).generate_all()["ngramas"]
        # 40 bigramas distintos, mas a saída é limitada a 30.
        self.assertEqual(len(ngramas["bigramas"]), 30)


# Pools de palavras para os corpos gerados no teste de propriedade de n-gramas.
# - ``_CONTENT_WORDS``: termos de conteúdo com >= 2 caracteres, garantidamente
#   fora do conjunto de stop words (filtrados contra o recurso real).
# - ``_STOP_TOKENS``: stop words reais com >= 2 caracteres, de modo que
#   sobrevivam ao filtro de comprimento da engine e sejam descartadas apenas
#   pela regra de stop words (R16.3).
_NGRAMA_STOP_WORDS = get_stop_words()
_CONTENT_WORDS = [
    w
    for w in (
        "gato",
        "cachorro",
        "casa",
        "preto",
        "branco",
        "verde",
        "azul",
        "mesa",
        "livro",
        "carro",
        "praia",
        "musica",
        "janela",
        "estrada",
    )
    if w not in _NGRAMA_STOP_WORDS
]
_STOP_TOKENS = sorted(w for w in _NGRAMA_STOP_WORDS if len(w) >= 2)

# Cada token do corpo é sorteado de conteúdo ou de stop words, garantindo que
# stop words apareçam misturadas às palavras de conteúdo.
_ngrama_token = st.one_of(st.sampled_from(_CONTENT_WORDS), st.sampled_from(_STOP_TOKENS))
_ngrama_body = st.lists(_ngrama_token, max_size=8).map(" ".join)
_ngrama_bodies = st.lists(_ngrama_body, max_size=15)


# Feature: melhorias-analise-e-projeto, Property 15: Bigramas e trigramas são filtrados e ordenados
@settings(max_examples=200)
@given(bodies=_ngrama_bodies)
def test_property_ngramas_filtrados_e_ordenados(bodies):
    """Para qualquer conjunto de mensagens, nenhum bigrama ou trigrama produzido deve conter
    stop words, e as listas de bigramas e trigramas devem estar ordenadas por frequência em
    ordem decrescente.

    Cada corpo de mensagem mistura palavras de conteúdo (nunca stop words) com stop words reais
    do recurso de idioma (pt), garantindo que stop words apareçam no texto de entrada. A engine
    deve removê-las antes de formar os n-gramas (R16.3) e expor as listas ordenadas por
    contagem decrescente (R16.4).

    Validates: Requirements 16.1, 16.2, 16.3, 16.4
    """
    msgs = [_make_msg(author="user1", body=body) for body in bodies]
    thread = _make_thread(messages=msgs)
    ngramas = ChatStatistics([thread], "user1", "100").generate_all()["ngramas"]

    stop_words = get_stop_words()

    # R16.3: nenhum token de qualquer bigrama/trigrama é uma stop word.
    for item in ngramas["bigramas"] + ngramas["trigramas"]:
        for token in item["ngrama"].split():
            assert token not in stop_words, f"stop word '{token}' em '{item['ngrama']}'"

    # R16.1, R16.2, R16.4: as listas estão ordenadas por contagem decrescente.
    for lista in (ngramas["bigramas"], ngramas["trigramas"]):
        contagens = [item["contagem"] for item in lista]
        assert contagens == sorted(contagens, reverse=True)


class TestLinguisticoStats(unittest.TestCase):
    """Testes para métricas linguísticas por participante (R17)"""

    def test_empty_returns_empty_list(self):
        # Conjunto sem mensagens reporta lista vazia sem erro.
        thread = _make_thread(messages=[])
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        self.assertEqual(linguistico, [])

    def test_razao_pergunta_afirmacao(self):
        # Duas perguntas e uma afirmação -> razão 2 / 1 == 2.0.
        msgs = [
            _make_msg(author="user1", body="tudo bem?"),
            _make_msg(author="user1", body="você vem?"),
            _make_msg(author="user1", body="estou indo"),
        ]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        self.assertEqual(user1["razao_pergunta_afirmacao"], 2.0)

    def test_razao_sem_afirmacoes_usa_contagem_de_perguntas(self):
        # Sem afirmações, a razão equivale ao número de perguntas (divisão por 1).
        msgs = [
            _make_msg(author="user1", body="oi?"),
            _make_msg(author="user1", body="tudo certo?"),
            _make_msg(author="user1", body="vem?"),
        ]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        self.assertEqual(user1["razao_pergunta_afirmacao"], 3.0)

    def test_riqueza_vocabulario_no_intervalo(self):
        # "gato gato cachorro": 2 tokens únicos / 3 totais == 0.6667.
        msgs = [_make_msg(author="user1", body="gato gato cachorro")]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        self.assertGreaterEqual(user1["riqueza_vocabulario"], 0.0)
        self.assertLessEqual(user1["riqueza_vocabulario"], 1.0)
        self.assertEqual(user1["riqueza_vocabulario"], round(2 / 3, 4))

    def test_riqueza_zero_sem_tokens(self):
        # Mensagem sem tokens válidos (apenas pontuação) -> riqueza 0.0.
        msgs = [_make_msg(author="user1", body="...")]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        self.assertEqual(user1["riqueza_vocabulario"], 0.0)

    def test_distribuicao_horaria_soma_iguala_mensagens_datadas(self):
        # Mensagens em faixas distintas; a soma deve igualar o nº de datadas.
        msgs = [
            _make_msg(author="user1", body="a", sent=datetime(2024, 1, 1, 2, 0, 0)),
            _make_msg(author="user1", body="b", sent=datetime(2024, 1, 1, 9, 0, 0)),
            _make_msg(author="user1", body="c", sent=datetime(2024, 1, 1, 15, 0, 0)),
            _make_msg(author="user1", body="d", sent=datetime(2024, 1, 1, 20, 0, 0)),
            # Sem data: não entra na distribuição horária.
            Message(author="user1", author_id="100", platform="instagram", sent=None, body="e"),
        ]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        distribuicao = user1["distribuicao_horaria"]
        self.assertEqual(distribuicao, {"madrugada": 1, "manha": 1, "tarde": 1, "noite": 1})
        # Quatro mensagens datadas -> soma das faixas igual a 4.
        self.assertEqual(sum(distribuicao.values()), 4)

    def test_perfil_corresponde_a_faixa_predominante(self):
        # Predomínio na madrugada -> perfil "notívago".
        msgs = [
            _make_msg(author="user1", body="a", sent=datetime(2024, 1, 1, 2, 0, 0)),
            _make_msg(author="user1", body="b", sent=datetime(2024, 1, 1, 3, 0, 0)),
            _make_msg(author="user1", body="c", sent=datetime(2024, 1, 1, 9, 0, 0)),
        ]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        self.assertEqual(user1["perfil_horario"], "notívago")

    def test_perfil_indefinido_sem_mensagens_datadas(self):
        # Sem mensagens datadas, o perfil é "indefinido".
        msgs = [
            Message(author="user1", author_id="100", platform="instagram", sent=None, body="oi")
        ]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        self.assertEqual(user1["perfil_horario"], "indefinido")
        self.assertEqual(
            user1["distribuicao_horaria"],
            {
                "madrugada": 0,
                "manha": 0,
                "tarde": 0,
                "noite": 0,
            },
        )

    def test_mapeamento_de_perfis_por_faixa(self):
        # Cada faixa predominante mapeia para o rótulo PT-BR documentado.
        casos = {
            9: "madrugador",  # manhã
            15: "vespertino",  # tarde
            20: "noturno",  # noite
        }
        for hora, perfil_esperado in casos.items():
            msgs = [_make_msg(author="user1", body="a", sent=datetime(2024, 1, 1, hora, 0, 0))]
            thread = _make_thread(messages=msgs)
            linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
            user1 = next(p for p in linguistico if p["nome"] == "user1")
            self.assertEqual(user1["perfil_horario"], perfil_esperado)

    def test_ignora_chamadas_e_removidas_na_razao(self):
        # Chamadas e removidas não contam como pergunta nem afirmação.
        msgs = [
            _make_msg(author="user1", body="estou aqui"),
            _make_msg(author="user1", body="ligando?", is_call=True),
            _make_msg(author="user1", body="apagada?", removed_by_sender=True),
        ]
        thread = _make_thread(messages=msgs)
        linguistico = ChatStatistics([thread]).generate_all()["linguistico"]
        user1 = next(p for p in linguistico if p["nome"] == "user1")
        # Apenas uma afirmação válida, nenhuma pergunta -> razão 0.0.
        self.assertEqual(user1["razao_pergunta_afirmacao"], 0.0)


# Mapeamento faixa horária -> rótulo de perfil, espelhando `_FAIXAS_HORARIAS`
# em stats.py. A ordem da tupla também define o desempate (primeira faixa vence).
_FAIXA_PARA_PERFIL = (
    ("madrugada", "notívago"),
    ("manha", "madrugador"),
    ("tarde", "vespertino"),
    ("noite", "noturno"),
)


# Feature: melhorias-analise-e-projeto, Property 16: Métricas linguísticas respeitam suas faixas e conservação
@settings(max_examples=200)
@given(msgs=st.lists(messages(), max_size=20))
def test_property_linguistico_faixas_e_conservacao(msgs):
    """Para qualquer participante, a riqueza de vocabulário (razão type-token) deve estar no
    intervalo [0, 1]; a razão pergunta/afirmação deve ser não-negativa; a soma da distribuição
    de mensagens por faixa horária deve igualar o total de mensagens datadas daquele
    participante; e a classificação de perfil deve corresponder à faixa horária predominante
    (ou "indefinido" quando o participante não tem mensagens datadas). Além disso, todo
    participante presente na entrada deve aparecer na saída.

    Reutiliza o gerador compartilhado `messages()` (tests/strategies.py), que cobre os casos de
    borda exigidos pelo design (corpos vazios/whitespace, chamadas, removidas, datas variadas e
    conteúdo não-ASCII).

    Validates: Requirements 17.1, 17.2, 17.3, 17.4
    """
    thread = _make_thread(messages=msgs)
    linguistico = ChatStatistics([thread]).generate_all()["linguistico"]

    # Conservação de participantes: todo autor presente na entrada aparece na saída.
    autores_entrada = {m.author for m in msgs}
    autores_saida = {p["nome"] for p in linguistico}
    assert autores_saida == autores_entrada

    # Total de mensagens datadas por autor (independe de conteúdo/chamada/remoção).
    datadas_por_autor = Counter(m.author for m in msgs if m.sent is not None)

    faixas = [faixa for faixa, _ in _FAIXA_PARA_PERFIL]
    perfil_por_faixa = dict(_FAIXA_PARA_PERFIL)

    for participante in linguistico:
        nome = participante["nome"]

        # R17.2: riqueza de vocabulário (type-token) sempre em [0, 1].
        riqueza = participante["riqueza_vocabulario"]
        assert 0.0 <= riqueza <= 1.0, f"riqueza fora de [0,1]: {riqueza}"

        # R17.1: razão pergunta/afirmação é não-negativa.
        assert participante["razao_pergunta_afirmacao"] >= 0.0

        # R17.3: a distribuição cobre exatamente as quatro faixas, com contagens
        # não-negativas, e sua soma iguala o total de mensagens datadas do autor.
        distribuicao = participante["distribuicao_horaria"]
        assert set(distribuicao) == set(faixas)
        assert all(contagem >= 0 for contagem in distribuicao.values())
        assert sum(distribuicao.values()) == datadas_por_autor[nome]

        # R17.4: o perfil corresponde à faixa predominante (desempate pela ordem
        # das faixas); "indefinido" quando não há mensagens datadas.
        if any(distribuicao.values()):
            faixa_predominante = max(faixas, key=lambda faixa: distribuicao[faixa])
            assert participante["perfil_horario"] == perfil_por_faixa[faixa_predominante]
        else:
            assert participante["perfil_horario"] == "indefinido"


class TestSentimentoStats(unittest.TestCase):
    """Testes para a análise de sentimento offline opcional (R18)."""

    def setUp(self):
        # Salva o estado original da flag de sentimento para restaurar depois,
        # evitando vazamento de configuração entre testes.
        from meta_chat_exporter.config import config as _cfg

        self._cfg = _cfg
        self._original = _cfg.get("sentiment_enabled")

    def tearDown(self):
        # Restaura a configuração original sem persistir em disco.
        self._cfg._data["sentiment_enabled"] = self._original

    def _set_enabled(self, enabled):
        # Altera apenas o dicionário em memória (não grava config.json).
        self._cfg._data["sentiment_enabled"] = enabled

    def test_omitido_quando_desabilitado(self):
        # R18.3: quando desabilitado, a chave 'sentimento' não aparece na saída.
        self._set_enabled(False)
        msgs = [_make_msg(author="user1", body="que dia ótimo, adorei!")]
        thread = _make_thread(messages=msgs)
        resultado = ChatStatistics([thread]).generate_all()
        self.assertNotIn("sentimento", resultado)

    def test_registrado_quando_habilitado(self):
        # R18.1/R18.4: quando habilitado, a família 'sentimento' é registrada.
        self._set_enabled(True)
        msgs = [_make_msg(author="user1", body="que dia ótimo, adorei!")]
        thread = _make_thread(messages=msgs)
        resultado = ChatStatistics([thread]).generate_all()
        self.assertIn("sentimento", resultado)
        self.assertIsInstance(resultado["sentimento"], list)

    def test_schema_campos_nome_e_distribuicao_tom(self):
        # O esquema da família exige exatamente os campos 'nome' e
        # 'distribuicao_tom' (advanced_stats_schema.py).
        self._set_enabled(True)
        msgs = [_make_msg(author="user1", body="tudo bem")]
        thread = _make_thread(messages=msgs)
        entrada = ChatStatistics([thread]).generate_all()["sentimento"][0]
        self.assertEqual(set(entrada.keys()), {"nome", "distribuicao_tom"})
        dist = entrada["distribuicao_tom"]
        self.assertEqual(set(dist.keys()), {"positivo", "neutro", "negativo", "total", "fracoes"})

    def test_classificacao_positiva(self):
        # Mensagem com termos positivos do léxico -> tom positivo.
        self._set_enabled(True)
        msgs = [_make_msg(author="user1", body="que dia maravilhoso, adorei muito!")]
        thread = _make_thread(messages=msgs)
        dist = ChatStatistics([thread]).generate_all()["sentimento"][0]["distribuicao_tom"]
        self.assertEqual(dist["positivo"], 1)
        self.assertEqual(dist["negativo"], 0)
        self.assertEqual(dist["neutro"], 0)

    def test_classificacao_negativa(self):
        # Mensagem com termos negativos do léxico -> tom negativo.
        self._set_enabled(True)
        msgs = [_make_msg(author="user1", body="que dia horrível, estou muito triste")]
        thread = _make_thread(messages=msgs)
        dist = ChatStatistics([thread]).generate_all()["sentimento"][0]["distribuicao_tom"]
        self.assertEqual(dist["negativo"], 1)
        self.assertEqual(dist["positivo"], 0)

    def test_classificacao_neutra_sem_termos(self):
        # Sem termos do léxico -> tom neutro.
        self._set_enabled(True)
        msgs = [_make_msg(author="user1", body="vou passar na padaria depois")]
        thread = _make_thread(messages=msgs)
        dist = ChatStatistics([thread]).generate_all()["sentimento"][0]["distribuicao_tom"]
        self.assertEqual(dist["neutro"], 1)
        self.assertEqual(dist["positivo"], 0)
        self.assertEqual(dist["negativo"], 0)

    def test_empate_resulta_em_neutro(self):
        # Empate entre positivos e negativos -> neutro.
        self._set_enabled(True)
        msgs = [_make_msg(author="user1", body="foi ótimo mas também horrível")]
        thread = _make_thread(messages=msgs)
        dist = ChatStatistics([thread]).generate_all()["sentimento"][0]["distribuicao_tom"]
        self.assertEqual(dist["neutro"], 1)

    def test_distribuicao_por_participante_e_fracoes(self):
        # A distribuição é reportada por participante (R18.4) e as frações
        # somam 1.0 quando há mensagens classificadas.
        self._set_enabled(True)
        msgs = [
            _make_msg(author="user1", body="adorei, perfeito"),  # positivo
            _make_msg(author="user1", body="que coisa horrível"),  # negativo
            _make_msg(author="user1", body="vou sair agora"),  # neutro
            _make_msg(author="user2", body="bom demais, incrível"),  # positivo
        ]
        thread = _make_thread(messages=msgs)
        resultado = ChatStatistics([thread]).generate_all()["sentimento"]
        por_nome = {p["nome"]: p["distribuicao_tom"] for p in resultado}

        self.assertEqual(por_nome["user1"]["total"], 3)
        self.assertEqual(por_nome["user1"]["positivo"], 1)
        self.assertEqual(por_nome["user1"]["negativo"], 1)
        self.assertEqual(por_nome["user1"]["neutro"], 1)
        soma_fracoes = sum(por_nome["user1"]["fracoes"].values())
        # Frações são arredondadas a 4 casas, então a soma pode divergir de 1.0
        # por um resíduo de arredondamento (ex.: três terços -> 0.9999).
        self.assertAlmostEqual(soma_fracoes, 1.0, places=2)

        self.assertEqual(por_nome["user2"]["positivo"], 1)
        self.assertEqual(por_nome["user2"]["total"], 1)

    def test_ignora_chamadas_e_removidas(self):
        # Chamadas e removidas não entram na classificação (total não as conta).
        self._set_enabled(True)
        msgs = [
            _make_msg(author="user1", body="ótimo"),
            _make_msg(author="user1", body="adorei", is_call=True),
            _make_msg(author="user1", body="horrível", removed_by_sender=True),
        ]
        thread = _make_thread(messages=msgs)
        dist = ChatStatistics([thread]).generate_all()["sentimento"][0]["distribuicao_tom"]
        self.assertEqual(dist["total"], 1)
        self.assertEqual(dist["positivo"], 1)

    def test_nome_ja_redigido_e_preservado(self):
        # Segue o mesmo padrão dos demais _stats_*: o nome exposto é exatamente
        # o autor presente na Data_Layer (já redigido a montante por R4), sem
        # transformação adicional na engine.
        self._set_enabled(True)
        msgs = [_make_msg(author="Pessoa 1", body="legal")]
        thread = _make_thread(messages=msgs)
        resultado = ChatStatistics([thread]).generate_all()["sentimento"]
        self.assertEqual(resultado[0]["nome"], "Pessoa 1")

    def test_conjunto_vazio_retorna_lista_vazia(self):
        # Conjunto sem mensagens reporta lista vazia sem erro.
        self._set_enabled(True)
        thread = _make_thread(messages=[])
        resultado = ChatStatistics([thread]).generate_all()["sentimento"]
        self.assertEqual(resultado, [])


# Feature: melhorias-analise-e-projeto, Property 17: Análise de sentimento é offline e condicional
@settings(max_examples=200)
@given(msgs=st.lists(messages(), max_size=20))
def test_property_sentimento_offline_e_condicional(msgs):
    """Para qualquer conjunto de mensagens:

    - Quando a análise de sentimento está habilitada, a família ``sentimento`` é
      registrada (R18.1) e a distribuição de tom é reportada por participante
      (R18.4) usando apenas as três categorias do léxico local — positivo, neutro
      e negativo (R18.2). Para cada participante: as contagens são não-negativas;
      ``positivo + neutro + negativo`` é igual ao ``total``; o total é exatamente o
      número de mensagens classificáveis daquele autor (corpo não vazio, não
      chamada, não removida); as frações somam ~1.0 quando há mensagens
      classificadas e são todas 0.0 caso contrário. Todo autor presente na entrada
      aparece na saída.
    - Quando desabilitada, a chave ``sentimento`` é omitida da saída (R18.3).

    A classificação é offline por construção (léxico embutido em stats.py, sem
    qualquer chamada de rede — R18.2).

    Reutiliza o gerador compartilhado `messages()` (tests/strategies.py), que cobre
    os casos de borda do design (corpos vazios/whitespace, chamadas, removidas,
    datas variadas e conteúdo não-ASCII).

    Validates: Requirements 18.1, 18.2, 18.3, 18.4
    """
    from meta_chat_exporter.config import config as _cfg

    original = _cfg.get("sentiment_enabled")
    thread = _make_thread(messages=msgs)

    # Autores presentes na entrada.
    autores_entrada = {m.author for m in msgs}
    # Total de mensagens classificáveis por autor (mesma regra de _stats_sentimento:
    # corpo não vazio, não chamada e não removida).
    classificaveis_por_autor = Counter(
        m.author for m in msgs if m.body and not m.is_call and not m.removed_by_sender
    )
    tons_validos = {"positivo", "neutro", "negativo"}

    try:
        # --- Habilitado: família registrada e invariantes da distribuição ---
        _cfg._data["sentiment_enabled"] = True
        resultado = ChatStatistics([thread]).generate_all()
        assert "sentimento" in resultado
        sentimento = resultado["sentimento"]
        assert isinstance(sentimento, list)

        # Conservação de participantes: todo autor da entrada aparece na saída.
        autores_saida = {p["nome"] for p in sentimento}
        assert autores_saida == autores_entrada

        for participante in sentimento:
            nome = participante["nome"]
            dist = participante["distribuicao_tom"]

            positivo = dist["positivo"]
            neutro = dist["neutro"]
            negativo = dist["negativo"]
            total = dist["total"]
            fracoes = dist["fracoes"]

            # R18.2: apenas as categorias do léxico local são usadas.
            assert set(fracoes) == tons_validos

            # Contagens não-negativas.
            assert positivo >= 0 and neutro >= 0 and negativo >= 0

            # A soma das contagens por tom é igual ao total reportado.
            assert positivo + neutro + negativo == total

            # O total é exatamente o número de mensagens classificáveis do autor.
            assert total == classificaveis_por_autor[nome]

            # Frações: somam ~1.0 quando há mensagens; todas 0.0 quando não há.
            if total:
                assert abs(sum(fracoes.values()) - 1.0) < 0.01
                assert all(0.0 <= f <= 1.0 for f in fracoes.values())
            else:
                assert all(f == 0.0 for f in fracoes.values())

        # --- Desabilitado: a família 'sentimento' é omitida (R18.3) ---
        _cfg._data["sentiment_enabled"] = False
        resultado_off = ChatStatistics([thread]).generate_all()
        assert "sentimento" not in resultado_off
    finally:
        # Restaura a configuração original sem persistir em disco.
        _cfg._data["sentiment_enabled"] = original


class TestInsightsStats(unittest.TestCase):
    """Testes para o sumário de insights automáticos (R22)."""

    def _build_dm(self):
        # DM com respostas alternadas suficientes para gerar tempo de resposta
        # (mínimo de 3 respostas por autor) e atividade temporal.
        base = datetime(2024, 3, 4, 10, 0, 0)  # segunda-feira
        msgs = []
        # user1 envia mensagens iniciais consecutivas (fica mais ativo no total),
        # sem gerar transições de autor.
        for i in range(3):
            msgs.append(
                _make_msg(author="user1", body=f"abre{i}", sent=base + timedelta(minutes=i))
            )
        # Alternância user2/user1 garantindo >= 4 transições para cada autor.
        alternancia = [
            ("user2", 10),
            ("user1", 11),
            ("user2", 20),
            ("user1", 21),
            ("user2", 30),
            ("user1", 31),
            ("user2", 40),
            ("user1", 41),
        ]
        for autor, minuto in alternancia:
            msgs.append(
                _make_msg(
                    author=autor,
                    body=f"{autor}@{minuto}",
                    sent=base + timedelta(minutes=minuto),
                )
            )
        return _make_thread(messages=msgs)

    def test_insights_presente_no_generate_all_com_campos_do_esquema(self):
        thread = self._build_dm()
        stats = ChatStatistics([thread], "user1", "100").generate_all()
        self.assertIn("insights", stats)
        insights = stats["insights"]
        self.assertIsInstance(insights, dict)
        # Os campos do esquema (advanced_stats_schema) devem ser as únicas chaves
        # permitidas; ao menos uma deve estar presente para este fixture.
        campos_esquema = {"picos_atividade", "contato_mais_ativo", "resposta_mais_rapida"}
        self.assertTrue(set(insights).issubset(campos_esquema))
        self.assertTrue(set(insights))  # não vazio para dados reais

    def test_contato_mais_ativo_correto(self):
        thread = self._build_dm()
        stats = ChatStatistics([thread], "user1", "100").generate_all()
        contato = stats["insights"]["contato_mais_ativo"]
        # user1 tem mais mensagens que user2.
        self.assertEqual(contato["nome"], "user1")
        participantes = stats["por_participante"]
        esperado = max(participantes, key=lambda p: p["mensagens"])
        self.assertEqual(contato["mensagens"], esperado["mensagens"])

    def test_resposta_mais_rapida_corresponde_menor_mediana(self):
        thread = self._build_dm()
        stats = ChatStatistics([thread], "user1", "100").generate_all()
        tempo_resposta = stats["tempo_resposta"]
        self.assertTrue(tempo_resposta)  # garante que há dados de resposta
        esperado = min(tempo_resposta, key=lambda r: r["mediana_segundos"])
        resposta = stats["insights"]["resposta_mais_rapida"]
        self.assertEqual(resposta["nome"], esperado["nome"])
        self.assertEqual(resposta["mediana_segundos"], esperado["mediana_segundos"])

    def test_picos_atividade_refletem_temporal_e_horarios(self):
        thread = self._build_dm()
        stats = ChatStatistics([thread], "user1", "100").generate_all()
        picos = stats["insights"]["picos_atividade"]
        # A hora de pico deve coincidir com horarios.hora_mais_ativa.
        self.assertEqual(picos["hora"], stats["horarios"]["hora_mais_ativa"])
        # O dia de pico deve coincidir com temporal.dia_mais_ativo.
        self.assertEqual(picos["dia_semana"], stats["temporal"]["dia_mais_ativo"])
        # O mês de pico deve ser o de maior volume em temporal.por_mes.
        mes_esperado = max(stats["temporal"]["por_mes"], key=lambda m: m["total"])
        self.assertEqual(picos["mes"]["mes"], mes_esperado["mes"])
        self.assertEqual(picos["mes"]["total"], mes_esperado["total"])

    def test_conjunto_vazio_nao_gera_erro_e_insights_vazio(self):
        thread = _make_thread(messages=[])
        stats = ChatStatistics([thread], "user1", "100").generate_all()
        self.assertIn("insights", stats)
        self.assertEqual(stats["insights"], {})

    def test_itens_sem_dados_sao_omitidos(self):
        # Uma única mensagem: há contato mais ativo e picos, mas não há tempo de
        # resposta suficiente (mínimo de 3 respostas), então o item é omitido.
        msgs = [_make_msg(author="user1", body="oi", sent=datetime(2024, 1, 15, 10, 0))]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread], "user1", "100").generate_all()
        insights = stats["insights"]
        self.assertIn("contato_mais_ativo", insights)
        self.assertNotIn("resposta_mais_rapida", insights)


class TestStatsFilter(unittest.TestCase):
    """Testes para o recálculo filtrado do painel de estatísticas (R19)."""

    def _build_threads(self):
        t1 = _make_thread(
            thread_id="t1",
            name="Chat A",
            messages=[
                _make_msg(author="user1", body="jan", sent=datetime(2024, 1, 10, 9, 0)),
                _make_msg(author="user2", body="fev", sent=datetime(2024, 2, 10, 9, 0)),
            ],
        )
        t2 = _make_thread(
            thread_id="t2",
            name="Chat B",
            messages=[
                _make_msg(author="user3", body="mar", sent=datetime(2024, 3, 10, 9, 0)),
                _make_msg(author="user4", body="abr", sent=datetime(2024, 4, 10, 9, 0)),
            ],
        )
        return [t1, t2]

    def test_filtro_vazio_retorna_conjunto_global(self):
        engine = ChatStatistics(self._build_threads(), "user1", "100")
        filtrado = engine.filtrar(None)
        self.assertEqual(
            filtrado.generate_all()["resumo"]["total_mensagens"],
            engine.generate_all()["resumo"]["total_mensagens"],
        )

    def test_filtro_por_conversa_recalcula_sobre_subconjunto(self):
        engine = ChatStatistics(self._build_threads(), "user1", "100")
        from meta_chat_exporter.stats import StatsFilter

        filtrado = engine.filtrar(StatsFilter(thread_id="t1"))
        stats = filtrado.generate_all()
        self.assertEqual(stats["resumo"]["total_mensagens"], 2)
        self.assertEqual(stats["resumo"]["total_conversas"], 1)
        # Equivale a calcular diretamente sobre o subconjunto (apenas t1).
        subset = ChatStatistics([self._build_threads()[0]], "user1", "100").generate_all()
        self.assertEqual(stats["resumo"]["total_mensagens"], subset["resumo"]["total_mensagens"])

    def test_filtro_por_intervalo_de_datas(self):
        engine = ChatStatistics(self._build_threads(), "user1", "100")
        filtrado = engine.filtrar(
            {"data_inicio": datetime(2024, 2, 1), "data_fim": datetime(2024, 3, 31)}
        )
        stats = filtrado.generate_all()
        # Apenas fev (t1) e mar (t2) entram no intervalo.
        self.assertEqual(stats["resumo"]["total_mensagens"], 2)

    def test_filtro_combinado_conversa_e_datas(self):
        from meta_chat_exporter.stats import StatsFilter

        engine = ChatStatistics(self._build_threads(), "user1", "100")
        filtrado = engine.filtrar(
            StatsFilter(
                thread_id="t1",
                data_inicio=datetime(2024, 1, 1),
                data_fim=datetime(2024, 1, 31),
            )
        )
        stats = filtrado.generate_all()
        self.assertEqual(stats["resumo"]["total_mensagens"], 1)

    def test_filtro_sem_resultados_exibe_sem_dados(self):
        engine = ChatStatistics(self._build_threads(), "user1", "100")
        filtrado = engine.filtrar({"data_inicio": datetime(2030, 1, 1)})
        stats = filtrado.generate_all()
        self.assertEqual(stats["resumo"]["total_mensagens"], 0)
        # O renderer exibe indicação de conjunto vazio sem erro (R19.4).
        html = StatsReportRenderer.render_html_report(
            stats, filtro={"data_inicio": datetime(2030, 1, 1)}
        )
        self.assertIn("Nenhuma mensagem", html)

    def test_render_com_filtro_exibe_banner_e_insights(self):
        from meta_chat_exporter.stats import StatsFilter

        engine = ChatStatistics(self._build_threads(), "user1", "100")
        filtro = StatsFilter(thread_id="t1")
        stats = engine.filtrar(filtro).generate_all()
        html = StatsReportRenderer.render_html_report(stats, filtro=filtro)
        self.assertIn("Filtro aplicado", html)
        self.assertIn("stats-panel", html)


# Feature: melhorias-analise-e-projeto, Property 18: Filtros recalculam sobre o subconjunto correto
#
# Para qualquer conjunto de dados e filtro (por conversa e/ou intervalo de datas),
# as métricas recalculadas via `engine.filtrar(filtro).generate_all()` devem ser
# iguais às métricas calculadas diretamente sobre o subconjunto de mensagens
# correspondente ao filtro; sem filtro, devem coincidir com o conjunto global; e
# um filtro que não retorna mensagens deve reportar conjunto vazio sem erro.
# **Validates: Requirements 19.1, 19.2, 19.3, 19.4, 22.2, 22.3**
_INSIGHT_KEYS = {"picos_atividade", "contato_mais_ativo", "resposta_mais_rapida"}


@settings(max_examples=120, deadline=None)
@given(
    thread_list=st.lists(thread_strategy(), min_size=1, max_size=3),
    pick_thread=st.one_of(st.none(), st.integers(min_value=0, max_value=5)),
    use_inicio=st.booleans(),
    use_fim=st.booleans(),
    inicio_frac=st.floats(min_value=0.0, max_value=1.0),
    fim_frac=st.floats(min_value=0.0, max_value=1.0),
)
def test_property_filtros_recalculam_subconjunto(
    thread_list, pick_thread, use_inicio, use_fim, inicio_frac, fim_frac
):
    """Property 18: o recálculo filtrado equivale ao cálculo direto sobre o subconjunto.

    Deriva um filtro arbitrário (por conversa e/ou intervalo de datas) a partir
    dos dados gerados e verifica que ``engine.filtrar(filtro).generate_all()``
    produz exatamente as métricas calculadas sobre o subconjunto de mensagens
    que satisfazem o filtro. Também confirma: filtro vazio == conjunto global;
    filtro sem correspondência reporta zeros sem erro; e os insights contêm
    apenas as chaves permitidas, consistentes com as estatísticas filtradas.
    """
    from dataclasses import replace

    from meta_chat_exporter.stats import StatsFilter

    owner_username, owner_id = "owner", "1"
    engine = ChatStatistics(thread_list, owner_username, owner_id)
    global_stats = engine.generate_all()

    # --- (R19.3) Filtro vazio equivale ao conjunto global ----------------
    empty_stats = engine.filtrar(None).generate_all()
    assert empty_stats["resumo"]["total_mensagens"] == global_stats["resumo"]["total_mensagens"]
    assert empty_stats["resumo"]["total_conversas"] == global_stats["resumo"]["total_conversas"]

    # --- Derivar um filtro arbitrário a partir dos dados gerados ----------
    thread_id = None
    if pick_thread is not None and thread_list:
        thread_id = thread_list[pick_thread % len(thread_list)].thread_id

    dates = sorted({m.sent for t in thread_list for m in t.messages if m.sent is not None})
    data_inicio = None
    data_fim = None
    if dates:
        if use_inicio:
            data_inicio = dates[min(int(inicio_frac * (len(dates) - 1)), len(dates) - 1)]
        if use_fim:
            data_fim = dates[min(int(fim_frac * (len(dates) - 1)), len(dates) - 1)]
        if data_inicio is not None and data_fim is not None and data_inicio > data_fim:
            data_inicio, data_fim = data_fim, data_inicio

    filtro = StatsFilter(thread_id=thread_id, data_inicio=data_inicio, data_fim=data_fim)
    filtrado = engine.filtrar(filtro).generate_all()

    # --- (R19.1, R19.2) Equivalência com o subconjunto construído à parte --
    if filtro.is_empty():
        # Sem critérios, deve coincidir com o conjunto global.
        referencia = global_stats
    else:

        def _match_data(m):
            if data_inicio is None and data_fim is None:
                return True
            if m.sent is None:
                return False
            if data_inicio is not None and m.sent < data_inicio:
                return False
            if data_fim is not None and m.sent > data_fim:
                return False
            return True

        subset = []
        for t in thread_list:
            if thread_id is not None and t.thread_id != thread_id:
                continue
            msgs = [m for m in t.messages if _match_data(m)]
            if not msgs:
                continue
            subset.append(replace(t, messages=msgs))
        referencia = ChatStatistics(subset, owner_username, owner_id).generate_all()

    # Métricas representativas: resumo, por participante e temporal.
    assert filtrado["resumo"] == referencia["resumo"]
    assert filtrado["por_participante"] == referencia["por_participante"]
    assert filtrado["temporal"] == referencia["temporal"]

    # --- (R22.2, R22.3) Insights restritos ao esquema e consistentes ------
    insights = filtrado["insights"]
    assert isinstance(insights, dict)
    assert set(insights).issubset(_INSIGHT_KEYS)
    if "contato_mais_ativo" in insights:
        participantes = filtrado["por_participante"]
        assert participantes
        topo = max(participantes, key=lambda p: p["mensagens"])
        assert insights["contato_mais_ativo"]["mensagens"] == topo["mensagens"]

    # --- (R19.4) Filtro sem correspondência reporta zeros sem erro --------
    no_match = engine.filtrar(StatsFilter(data_inicio=datetime(2100, 1, 1))).generate_all()
    assert no_match["resumo"]["total_mensagens"] == 0
    assert no_match["resumo"]["total_conversas"] == 0
    assert no_match["insights"] == {}


# ---------------------------------------------------------------------------
# A1 / A2 / A4 — métricas de investigação
# ---------------------------------------------------------------------------


class TestTimelineContatosA1(unittest.TestCase):
    def test_primeira_ultima_e_total_por_contato(self):
        msgs = [
            _make_msg(author="alvo", body="oi", sent=datetime(2024, 1, 1, 10)),
            _make_msg(author="bob", body="ola", sent=datetime(2024, 1, 2, 11)),
            _make_msg(author="bob", body="tchau", sent=datetime(2024, 1, 5, 12)),
            _make_msg(author="carol", body="hi", sent=datetime(2024, 2, 1, 9)),
        ]
        thread = _make_thread(
            participants=[
                Participant("alvo", "instagram", "1"),
                Participant("bob", "instagram", "2"),
                Participant("carol", "instagram", "3"),
            ],
            messages=msgs,
        )
        stats = ChatStatistics([thread], owner_username="alvo").generate_all()
        tl = stats["timeline_contatos"]
        by_name = {row["nome"]: row for row in tl}
        self.assertIn("bob", by_name)
        self.assertIn("carol", by_name)
        self.assertNotIn("alvo", by_name)
        self.assertEqual(by_name["bob"]["total_mensagens"], 2)
        self.assertEqual(by_name["bob"]["primeira_msg"], "02/01/2024 11:00")
        self.assertEqual(by_name["bob"]["ultima_msg"], "05/01/2024 12:00")
        self.assertEqual(by_name["carol"]["total_mensagens"], 1)

    def test_sem_owner_retorna_vazio(self):
        thread = _make_thread(messages=[_make_msg(author="bob")])
        stats = ChatStatistics([thread], owner_username="").generate_all()
        self.assertEqual(stats["timeline_contatos"], [])


class TestAtividadeNoturnaA2(unittest.TestCase):
    def test_conta_apenas_00h_a_05h(self):
        msgs = [
            _make_msg(author="alvo", body="n1", sent=datetime(2024, 1, 1, 0, 30)),
            _make_msg(author="bob", body="n2", sent=datetime(2024, 1, 1, 5, 59)),
            _make_msg(author="bob", body="dia", sent=datetime(2024, 1, 1, 6, 0)),
            _make_msg(author="carol", body="tarde", sent=datetime(2024, 1, 1, 14)),
        ]
        thread = _make_thread(messages=msgs)
        stats = ChatStatistics([thread], owner_username="alvo").generate_all()
        noturna = stats["atividade_noturna"]
        self.assertEqual(noturna["total_noturna"], 2)
        by_name = {r["nome"]: r["mensagens"] for r in noturna["por_autor"]}
        self.assertEqual(by_name["alvo"], 1)
        self.assertEqual(by_name["bob"], 1)
        self.assertNotIn("carol", by_name)


class TestTaxaRespostaA4(unittest.TestCase):
    def test_resposta_pula_rajada_mesmo_autor(self):
        # alvo manda 2 msgs seguidas; bob responde em <24h → contato respondeu 1
        # bob manda 1; alvo responde → alvo respondeu 1
        msgs = [
            _make_msg(author="alvo", body="a1", sent=datetime(2024, 1, 1, 10, 0)),
            _make_msg(author="alvo", body="a2", sent=datetime(2024, 1, 1, 10, 1)),
            _make_msg(author="bob", body="b1", sent=datetime(2024, 1, 1, 10, 5)),
            _make_msg(author="alvo", body="a3", sent=datetime(2024, 1, 1, 10, 10)),
        ]
        thread = _make_thread(
            participants=[
                Participant("alvo", "instagram", "1"),
                Participant("bob", "instagram", "2"),
            ],
            messages=msgs,
        )
        rows = ChatStatistics([thread], owner_username="alvo").generate_all()["taxa_resposta"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["nome"], "bob")
        self.assertEqual(row["msgs_alvo"], 3)
        self.assertEqual(row["msgs_contato"], 1)
        # a1 e a2: próxima de outro autor é b1 (rajada pulada) → 2 respostas do contato
        # a3: sem resposta posterior
        self.assertEqual(row["respostas_contato"], 2)
        # b1: próxima de outro autor é a3 → 1 resposta do alvo
        self.assertEqual(row["respostas_alvo"], 1)
        self.assertEqual(row["taxa_resposta_alvo"], 100.0)
        self.assertAlmostEqual(row["taxa_resposta_contato"], 66.7, places=1)

    def test_grupo_excluido(self):
        thread = _make_thread(
            participants=[
                Participant("alvo", "instagram", "1"),
                Participant("bob", "instagram", "2"),
                Participant("carol", "instagram", "3"),
            ],
            messages=[
                _make_msg(author="alvo", body="x", sent=datetime(2024, 1, 1, 10)),
                _make_msg(author="bob", body="y", sent=datetime(2024, 1, 1, 11)),
            ],
        )
        rows = ChatStatistics([thread], owner_username="alvo").generate_all()["taxa_resposta"]
        self.assertEqual(rows, [])


class TestTimelineLinksA8(unittest.TestCase):
    def test_links_ordenados_cronologicamente(self):
        msgs = [
            _make_msg(
                author="bob",
                share_url="https://b.example/x",
                sent=datetime(2024, 2, 1, 10),
            ),
            _make_msg(
                author="alvo",
                share_url="https://a.example/y",
                sent=datetime(2024, 1, 1, 10),
            ),
        ]
        thread = _make_thread(messages=msgs)
        links = ChatStatistics([thread], owner_username="alvo").generate_all()["timeline_links"]
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["dominio"], "a.example")
        self.assertEqual(links[1]["dominio"], "b.example")
        self.assertEqual(links[0]["autor"], "alvo")


class TestDominanciaGrupoA9(unittest.TestCase):
    def test_dominante_e_percentual(self):
        msgs = [
            _make_msg(author="alice", body="1"),
            _make_msg(author="alice", body="2"),
            _make_msg(author="alice", body="3"),
            _make_msg(author="bob", body="4"),
        ]
        thread = _make_thread(
            participants=[
                Participant("alice", "instagram", "1"),
                Participant("bob", "instagram", "2"),
                Participant("carol", "instagram", "3"),
            ],
            messages=msgs,
        )
        rows = ChatStatistics([thread], owner_username="alice").generate_all()["dominancia_grupo"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["dominante"], "alice")
        self.assertEqual(rows[0]["pct_dominante"], 75.0)

    def test_dm_nao_entra(self):
        thread = _make_thread(
            participants=[
                Participant("alice", "instagram", "1"),
                Participant("bob", "instagram", "2"),
            ],
            messages=[_make_msg(author="alice"), _make_msg(author="bob")],
        )
        rows = ChatStatistics([thread], owner_username="alice").generate_all()["dominancia_grupo"]
        self.assertEqual(rows, [])


class TestMidiaPorContatoA10(unittest.TestCase):
    def test_tipo_predominante(self):
        from meta_chat_exporter.models import Attachment

        msgs = [
            _make_msg(
                author="bob",
                attachments=[
                    Attachment("a.jpg", "image/jpeg"),
                    Attachment("b.jpg", "image/jpeg"),
                ],
            ),
            _make_msg(author="bob", share_url="https://x.com/1"),
            _make_msg(
                author="carol",
                attachments=[Attachment("v.mp4", "video/mp4")],
            ),
        ]
        thread = _make_thread(messages=msgs)
        rows = ChatStatistics([thread], owner_username="alvo").generate_all()["midia_por_contato"]
        by_name = {r["nome"]: r for r in rows}
        self.assertEqual(by_name["bob"]["fotos"], 2)
        self.assertEqual(by_name["bob"]["links"], 1)
        self.assertEqual(by_name["bob"]["tipo_predominante"], "fotos")
        self.assertEqual(by_name["carol"]["videos"], 1)


class TestVelocidadeConversaA5(unittest.TestCase):
    def test_sessoes_ativas_msgs_por_hora(self):
        # 3 msgs em 6 minutos na mesma sessão → 30 msgs/h
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            _make_msg(author="a", body="1", sent=base),
            _make_msg(author="b", body="2", sent=base + timedelta(minutes=3)),
            _make_msg(author="a", body="3", sent=base + timedelta(minutes=6)),
        ]
        thread = _make_thread(messages=msgs)
        rows = ChatStatistics([thread], owner_username="a").generate_all()["velocidade_conversa"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["num_sessoes"], 1)
        self.assertEqual(rows[0]["total_msgs_ativas"], 3)
        self.assertEqual(rows[0]["msgs_por_hora_pico"], 30.0)

    def test_gap_quebra_sessao(self):
        base = datetime(2024, 1, 1, 10, 0, 0)
        msgs = [
            _make_msg(author="a", body="1", sent=base),
            _make_msg(author="b", body="2", sent=base + timedelta(minutes=5)),
            # gap de 2h → nova sessão
            _make_msg(author="a", body="3", sent=base + timedelta(hours=2)),
            _make_msg(author="b", body="4", sent=base + timedelta(hours=2, minutes=5)),
        ]
        thread = _make_thread(messages=msgs)
        rows = ChatStatistics([thread], owner_username="a").generate_all()["velocidade_conversa"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["num_sessoes"], 2)


class TestIniciadoresA3(unittest.TestCase):
    def test_primeira_mensagem_define_iniciador(self):
        base = datetime(2024, 2, 1, 9, 0, 0)
        msgs = [
            _make_msg(author="bob", body="oi", sent=base),
            _make_msg(author="alvo", body="e ai", sent=base + timedelta(minutes=1)),
        ]
        thread = _make_thread(messages=msgs)
        rows = ChatStatistics([thread], owner_username="alvo").generate_all()["iniciadores"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["iniciador"], "bob")
        self.assertEqual(rows[0]["data_inicio"], "01/02/2024 09:00")
        self.assertEqual(rows[0]["total_mensagens"], 2)


class TestRajadasA6(unittest.TestCase):
    def test_detecta_rajada_minima_3(self):
        base = datetime(2024, 3, 1, 12, 0, 0)
        msgs = [
            _make_msg(author="bob", body="1", sent=base),
            _make_msg(author="bob", body="2", sent=base + timedelta(seconds=1)),
            _make_msg(author="bob", body="3", sent=base + timedelta(seconds=2)),
            _make_msg(author="alvo", body="ok", sent=base + timedelta(seconds=3)),
            _make_msg(author="bob", body="4", sent=base + timedelta(seconds=4)),
        ]
        thread = _make_thread(messages=msgs)
        rows = ChatStatistics([thread], owner_username="alvo").generate_all()["rajadas"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["num_rajadas"], 1)
        self.assertEqual(rows[0]["maior_rajada"], 3)
        self.assertEqual(rows[0]["autor_mais_rajadas"], "bob")


class TestRemovidasPorAutorA7(unittest.TestCase):
    def test_conta_removidas_por_autor(self):
        msgs = [
            _make_msg(author="bob", body="x", removed_by_sender=True),
            _make_msg(author="bob", body="y", removed_by_sender=True),
            _make_msg(author="carol", body="z", removed_by_sender=True),
            _make_msg(author="bob", body="keep"),
        ]
        thread = _make_thread(messages=msgs)
        rows = ChatStatistics([thread], owner_username="alvo").generate_all()["removidas_por_autor"]
        by_name = {r["nome"]: r for r in rows}
        self.assertEqual(by_name["bob"]["removidas"], 2)
        self.assertEqual(by_name["bob"]["percentual"], 66.7)
        self.assertEqual(by_name["carol"]["removidas"], 1)


# ---------------------------------------------------------------------------
# Property 19: Single-pass equivale ao cálculo multi-passagem (R25)
# ---------------------------------------------------------------------------
#
# `ChatStatistics.generate_all()` percorre as mensagens UMA única vez
# (`_single_pass_accumulate`) alimentando acumuladores compartilhados que os
# métodos `_stats_*` consomem. Esta seção verifica que o resultado dessa
# passagem única é IDÊNTICO a uma implementação de referência multi-passagem,
# na qual CADA família de métricas é recomputada de forma independente,
# varrendo as mensagens por conta própria (sem reaproveitar os acumuladores da
# produção). Comparar `generate_all()` com `generate_all()` provaria apenas
# determinismo; por isso a referência abaixo é uma reconstrução independente.


def _multipass_reference(threads):
    """Reconstrói, de forma independente e multi-passagem, as famílias de
    métricas que a produção dobrou na passagem única.

    Cada família abaixo faz a sua própria varredura sobre ``all_messages``
    (ou sobre as threads, no caso de ``resumo``), replicando o contrato de
    saída documentado em ``stats.py`` — incluindo ordenação e desempates —
    sem tocar em ``_PassAccumulators``. O objetivo é servir de oráculo
    multi-passagem para a Property 19.
    """
    from collections import Counter, defaultdict

    from meta_chat_exporter.i18n import get_weekday_names

    all_messages = []
    for t in threads:
        all_messages.extend(t.messages)

    stop_words = get_stop_words()
    pontuacao = ".,!?;:()[]{}\"'…-_"
    modifiers = ("\ufe0f", "\u200d", "\ufe0e")
    faixas_tam = ChatStatistics._TAMANHO_FAIXAS
    faixas_hora = ChatStatistics._FAIXAS_HORARIAS
    weekday_names = get_weekday_names()
    # Instância usada apenas para reaproveitar a extração de clusters de emoji
    # (a tabela Unicode/biblioteca não faz parte do que a passagem única dobra).
    emoji_extractor = ChatStatistics([])

    def _corpo_util(m):
        return bool(m.body) and not m.is_call and not m.removed_by_sender

    ref = {}

    # --- resumo -----------------------------------------------------------
    first_date = last_date = None
    for m in all_messages:
        if m.sent:
            if first_date is None or m.sent < first_date:
                first_date = m.sent
            if last_date is None or m.sent > last_date:
                last_date = m.sent
    total_msgs = len(all_messages)
    participantes_unicos = set()
    for t in threads:
        for p in t.participants:
            participantes_unicos.add(p[0])
    if first_date and last_date:
        days = max((last_date - first_date).days, 1)
        msgs_per_day = total_msgs / days
    else:
        days = 0
        msgs_per_day = 0
    ref["resumo"] = {
        "total_mensagens": total_msgs,
        "total_conversas": len(threads),
        "total_participantes": len(participantes_unicos),
        "total_anexos": sum(len(m.attachments) for m in all_messages),
        "total_chamadas": sum(1 for m in all_messages if m.is_call),
        "total_temporarias": sum(1 for m in all_messages if m.disappearing),
        "total_removidas": sum(1 for m in all_messages if m.removed_by_sender),
        "total_compartilhamentos": sum(1 for m in all_messages if m.share_url),
        "primeira_mensagem": first_date.strftime("%d/%m/%Y %H:%M") if first_date else "N/A",
        "ultima_mensagem": last_date.strftime("%d/%m/%Y %H:%M") if last_date else "N/A",
        "periodo_dias": days,
        "media_mensagens_dia": round(msgs_per_day, 1),
        "total_reacoes": sum(1 for m in all_messages if m.is_reaction),
        "total_pagamentos": sum(1 for m in all_messages if m.has_payment),
        "total_eventos_grupo": sum(1 for m in all_messages if m.subscription_event),
        "total_dms": sum(1 for t in threads if len(t.participants) <= 2),
        "total_grupos": sum(1 for t in threads if len(t.participants) > 2),
        "msgs_dms": sum(len(t.messages) for t in threads if len(t.participants) <= 2),
        "msgs_grupos": sum(len(t.messages) for t in threads if len(t.participants) > 2),
    }

    # --- por_participante -------------------------------------------------
    ps = defaultdict(
        lambda: {
            "mensagens": 0,
            "caracteres": 0,
            "anexos": 0,
            "chamadas": 0,
            "audios": 0,
            "fotos": 0,
            "videos": 0,
            "links": 0,
            "reacoes": 0,
        }
    )
    for m in all_messages:
        d = ps[m.author]
        d["mensagens"] += 1
        d["caracteres"] += len(m.body or "")
        d["anexos"] += len(m.attachments)
        if m.is_call:
            d["chamadas"] += 1
        if m.share_url:
            d["links"] += 1
        if m.is_reaction:
            d["reacoes"] += 1
        for att in m.attachments:
            if "audio" in att.file_type:
                d["audios"] += 1
            elif "image" in att.file_type:
                d["fotos"] += 1
            elif "video" in att.file_type:
                d["videos"] += 1
    por_participante = [
        {
            "nome": name,
            "mensagens": d["mensagens"],
            "caracteres_total": d["caracteres"],
            "media_caracteres": round(d["caracteres"] / max(d["mensagens"], 1), 1),
            "anexos": d["anexos"],
            "chamadas": d["chamadas"],
            "audios": d["audios"],
            "fotos": d["fotos"],
            "videos": d["videos"],
            "links": d["links"],
            "reacoes": d["reacoes"],
        }
        for name, d in ps.items()
    ]
    por_participante.sort(key=lambda x: x["mensagens"], reverse=True)
    ref["por_participante"] = por_participante

    # --- temporal ---------------------------------------------------------
    por_mes = Counter()
    por_dia_semana = Counter()
    por_ano = Counter()
    for m in all_messages:
        if m.sent:
            por_mes[m.sent.strftime("%Y-%m")] += 1
            por_dia_semana[m.sent.weekday()] += 1
            por_ano[m.sent.year] += 1
    dia_mais_ativo = max(por_dia_semana, key=por_dia_semana.get) if por_dia_semana else 0
    ref["temporal"] = {
        "por_mes": [{"mes": k, "total": v} for k, v in sorted(por_mes.items())],
        "por_dia_semana": [
            {"dia": weekday_names[i], "total": por_dia_semana.get(i, 0)} for i in range(7)
        ],
        "por_ano": [{"ano": k, "total": v} for k, v in sorted(por_ano.items())],
        "dia_mais_ativo": weekday_names[dia_mais_ativo],
    }

    # --- midias -----------------------------------------------------------
    fotos = videos = audios = outros = 0
    for m in all_messages:
        for att in m.attachments:
            if "image" in att.file_type:
                fotos += 1
            elif "video" in att.file_type:
                videos += 1
            elif "audio" in att.file_type:
                audios += 1
            else:
                outros += 1
    ref["midias"] = {
        "fotos": fotos,
        "videos": videos,
        "audios": audios,
        "outros": outros,
        "total": fotos + videos + audios + outros,
    }

    # --- chamadas ---------------------------------------------------------
    c_total = c_perdidas = c_dur = 0
    c_tipos = Counter()
    for m in all_messages:
        if m.is_call:
            c_total += 1
            if m.call_missed:
                c_perdidas += 1
            c_dur += m.call_duration
            if m.call_type:
                c_tipos[m.call_type] += 1
    ref["chamadas"] = {
        "total": c_total,
        "perdidas": c_perdidas,
        "atendidas": c_total - c_perdidas,
        "duracao_total_segundos": c_dur,
        "duracao_total_formatada": f"{c_dur // 3600}h {(c_dur % 3600) // 60}m",
        "duracao_media_segundos": round(c_dur / max(c_total - c_perdidas, 1)),
        "por_tipo": dict(c_tipos),
    }

    # --- palavras ---------------------------------------------------------
    word_counter = Counter()
    total_words = 0
    for m in all_messages:
        if _corpo_util(m):
            for word in m.body.lower().split():
                clean = word.strip(pontuacao)
                if len(clean) >= 2 and clean not in stop_words:
                    word_counter[clean] += 1
                total_words += 1
    ref["palavras"] = {
        "total_palavras": total_words,
        "palavras_unicas": len(word_counter),
        "top_50": [{"palavra": w, "contagem": c} for w, c in word_counter.most_common(50)],
    }

    # --- horarios ---------------------------------------------------------
    por_hora = Counter()
    for m in all_messages:
        if m.sent:
            por_hora[m.sent.hour] += 1
    hora_mais_ativa = max(por_hora, key=por_hora.get) if por_hora else 0
    ref["horarios"] = {
        "por_hora": [{"hora": f"{h:02d}:00", "total": por_hora.get(h, 0)} for h in range(24)],
        "hora_mais_ativa": f"{hora_mais_ativa:02d}:00",
        "periodos": {
            "madrugada": sum(por_hora.get(h, 0) for h in range(0, 6)),
            "manha": sum(por_hora.get(h, 0) for h in range(6, 12)),
            "tarde": sum(por_hora.get(h, 0) for h in range(12, 18)),
            "noite": sum(por_hora.get(h, 0) for h in range(18, 24)),
        },
    }

    # --- heatmap ----------------------------------------------------------
    heatmap = [[0] * 24 for _ in range(7)]
    for m in all_messages:
        if m.sent:
            heatmap[m.sent.weekday()][m.sent.hour] += 1
    ref["heatmap"] = heatmap

    # --- atividade_noturna (A2, single-pass) ------------------------------
    noturna_autor = Counter()
    total_noturna = 0
    for m in all_messages:
        if m.sent and 0 <= m.sent.hour < 6:
            noturna_autor[m.author] += 1
            total_noturna += 1
    ref["atividade_noturna"] = {
        "total_noturna": total_noturna,
        "por_autor": [
            {"nome": n, "mensagens": c} for n, c in noturna_autor.most_common(20)
        ],
    }

    # --- reacoes ----------------------------------------------------------
    reacoes_autor = Counter()
    total_reacoes = 0
    for m in all_messages:
        if m.is_reaction:
            total_reacoes += 1
            reacoes_autor[m.author] += 1
    ref["reacoes"] = {
        "total": total_reacoes,
        "por_autor": [{"nome": n, "total": c} for n, c in reacoes_autor.most_common(10)],
    }

    # --- editadas ---------------------------------------------------------
    editadas_total = 0
    editadas_autor = Counter()
    for m in all_messages:
        if m.is_edited:
            editadas_total += 1
            editadas_autor[m.author] += 1
    ref["editadas"] = {
        "total": editadas_total,
        "por_autor": [{"nome": n, "total": c} for n, c in editadas_autor.most_common()],
    }

    # --- pagamentos / eventos / removidas / temporarias (por período) -----
    def _por_periodo(predicate):
        cnt = Counter()
        for m in all_messages:
            if m.sent and predicate(m):
                cnt[m.sent.strftime("%Y-%m")] += 1
        return {
            "total": sum(cnt.values()),
            "por_periodo": [{"periodo": p, "contagem": c} for p, c in sorted(cnt.items())],
        }

    ref["pagamentos"] = _por_periodo(lambda m: m.has_payment)
    ref["eventos_grupo"] = _por_periodo(
        lambda m: bool(m.subscription_event) or bool(m.subscription_users)
    )
    ref["removidas_temporal"] = _por_periodo(lambda m: m.removed_by_sender)
    ref["temporarias_temporal"] = _por_periodo(lambda m: m.disappearing)

    # --- dominios ---------------------------------------------------------
    por_dominio = Counter()
    for m in all_messages:
        if m.share_url:
            try:
                host = urlparse(m.share_url).hostname
            except ValueError:
                host = None
            if host:
                por_dominio[host] += 1
    ref["dominios"] = {
        "total": sum(por_dominio.values()),
        "por_dominio": [
            {"dominio": d, "contagem": c}
            for d, c in sorted(por_dominio.items(), key=lambda i: (-i[1], i[0]))
        ],
    }

    # --- tamanho_msgs -----------------------------------------------------
    dist_geral = Counter()
    dist_por_autor = defaultdict(Counter)
    total_chars = total_msgs_texto = 0
    for m in all_messages:
        if m.body:
            length = len(m.body)
            total_chars += length
            total_msgs_texto += 1
            for lo, hi, label in faixas_tam:
                if lo <= length <= hi:
                    dist_geral[label] += 1
                    dist_por_autor[m.author][label] += 1
                    break
    author_totals = Counter()
    for author, counts in dist_por_autor.items():
        author_totals[author] = sum(counts.values())
    top_authors = [a for a, _ in author_totals.most_common(8)]
    ref["tamanho_msgs"] = {
        "distribuicao": {label: dist_geral.get(label, 0) for _, _, label in faixas_tam},
        "faixas": [label for _, _, label in faixas_tam],
        "por_autor": {
            a: {label: dist_por_autor[a].get(label, 0) for _, _, label in faixas_tam}
            for a in top_authors
        },
        "media_chars": round(total_chars / max(total_msgs_texto, 1), 1),
        "total_msgs_com_texto": total_msgs_texto,
    }

    # --- ngramas ----------------------------------------------------------
    bigramas = Counter()
    trigramas = Counter()
    for m in all_messages:
        if _corpo_util(m):
            tokens = []
            for word in m.body.lower().split():
                clean = word.strip(pontuacao)
                if len(clean) >= 2 and clean not in stop_words:
                    tokens.append(clean)
            for i in range(len(tokens) - 1):
                bigramas[f"{tokens[i]} {tokens[i + 1]}"] += 1
            for i in range(len(tokens) - 2):
                trigramas[f"{tokens[i]} {tokens[i + 1]} {tokens[i + 2]}"] += 1

    def _ordenar_ngramas(contador, limite=30):
        return [
            {"ngrama": ng, "contagem": c}
            for ng, c in sorted(contador.items(), key=lambda i: (-i[1], i[0]))[:limite]
        ]

    ref["ngramas"] = {
        "bigramas": _ordenar_ngramas(bigramas),
        "trigramas": _ordenar_ngramas(trigramas),
    }

    # --- linguistico ------------------------------------------------------
    perguntas = Counter()
    afirmacoes = Counter()
    tokens_total = Counter()
    tokens_unicos = defaultdict(set)
    distrib = defaultdict(Counter)
    participantes = set()
    for m in all_messages:
        participantes.add(m.author)
        if m.sent:
            for faixa, horas, _ in faixas_hora:
                if m.sent.hour in horas:
                    distrib[m.author][faixa] += 1
                    break
        if _corpo_util(m):
            if "?" in m.body:
                perguntas[m.author] += 1
            else:
                afirmacoes[m.author] += 1
            for word in m.body.lower().split():
                clean = word.strip(pontuacao)
                if clean:
                    tokens_total[m.author] += 1
                    tokens_unicos[m.author].add(clean)
    linguistico = []
    for nome in participantes:
        n_perg = perguntas.get(nome, 0)
        n_afirm = afirmacoes.get(nome, 0)
        razao = n_perg / n_afirm if n_afirm else float(n_perg)
        total_tok = tokens_total.get(nome, 0)
        riqueza = len(tokens_unicos[nome]) / total_tok if total_tok else 0.0
        distribuicao = {faixa: distrib[nome].get(faixa, 0) for faixa, _, _ in faixas_hora}
        if any(distribuicao.values()):
            perfil = max(faixas_hora, key=lambda item: distribuicao[item[0]])[2]
        else:
            perfil = "indefinido"
        linguistico.append(
            {
                "nome": nome,
                "razao_pergunta_afirmacao": round(razao, 2),
                "riqueza_vocabulario": round(riqueza, 4),
                "distribuicao_horaria": distribuicao,
                "perfil_horario": perfil,
            }
        )
    linguistico.sort(key=lambda item: item["nome"])
    ref["linguistico"] = linguistico

    # --- emojis -----------------------------------------------------------
    emoji_counter = Counter()
    emoji_by_author = defaultdict(Counter)
    msgs_com_emoji = 0
    for m in all_messages:
        if _corpo_util(m):
            found = emoji_extractor._extract_emoji_clusters(m.body)
            if found:
                msgs_com_emoji += 1
                for cluster in found:
                    for ch in cluster:
                        if ch not in modifiers:
                            emoji_counter[ch] += 1
                            emoji_by_author[m.author][ch] += 1
    por_autor_emoji = []
    for author, counter in sorted(
        emoji_by_author.items(), key=lambda x: sum(x[1].values()), reverse=True
    )[:10]:
        por_autor_emoji.append(
            {
                "nome": author,
                "total": sum(counter.values()),
                "top_3": [e for e, _ in counter.most_common(3)],
            }
        )
    ref["emojis"] = {
        "total_emojis": sum(emoji_counter.values()),
        "emojis_unicos": len(emoji_counter),
        "msgs_com_emoji": msgs_com_emoji,
        "top_30": [{"emoji": e, "contagem": c} for e, c in emoji_counter.most_common(30)],
        "por_autor": por_autor_emoji,
    }

    return ref


# Famílias derivadas da iteração por mensagem que a passagem única dobrou.
_SINGLE_PASS_FAMILIES = (
    "resumo",
    "por_participante",
    "temporal",
    "midias",
    "chamadas",
    "palavras",
    "horarios",
    "heatmap",
    "atividade_noturna",
    "reacoes",
    "emojis",
    "editadas",
    "pagamentos",
    "eventos_grupo",
    "removidas_temporal",
    "temporarias_temporal",
    "dominios",
    "tamanho_msgs",
    "ngramas",
    "linguistico",
)


# Feature: melhorias-analise-e-projeto, Property 19: Single-pass equivale ao
# cálculo multi-passagem — para qualquer coleção de mensagens, o resultado de
# generate_all() (passagem única) deve ser igual ao resultado de uma
# implementação de referência multi-passagem para as mesmas entradas.
# Validates: Requirements 25.1, 25.2
@settings(max_examples=150, deadline=None)
@given(thread_list=st.lists(thread_strategy(), max_size=6))
def test_property_single_pass_equivale_multipass(thread_list):
    """A passagem única de generate_all() reproduz, família a família, o
    resultado de uma reconstrução multi-passagem independente das mesmas
    mensagens (R25.1, R25.2)."""
    single = ChatStatistics(thread_list).generate_all()
    reference = _multipass_reference(thread_list)

    for familia in _SINGLE_PASS_FAMILIES:
        assert single[familia] == reference[familia], (
            f"Divergência single-pass vs multi-pass na família '{familia}': "
            f"{single[familia]!r} != {reference[familia]!r}"
        )
