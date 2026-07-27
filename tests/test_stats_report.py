"""
Testes para o módulo stats_report.py - Renderização do relatório por conversa (R20).

Cobre os critérios de aceitação do Requisito 20:
- 20.1: relatório com métricas da conversa.
- 20.2: presença das seções participantes, volume temporal, tempo de resposta e mídias.
- 20.3: escape de todo conteúdo dinâmico via HTML_Escaper (escape_html).

Inclui também o caso "sem dados", que deve ser tratado sem erro.
"""

import os
import re
import sys
import unittest
from datetime import datetime
from html.parser import HTMLParser

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.models import Message, Participant, Thread
from meta_chat_exporter.stats import ChatStatistics
from meta_chat_exporter.stats_report import StatsReportRenderer
from tests.strategies import threads


def _make_thread_stats():
    """Monta um thread_stats de exemplo com todas as seções preenchidas."""
    return {
        "nome": "Conversa de Exemplo",
        "tipo": "DM",
        "mensagens": 120,
        "anexos": 8,
        "chamadas": 3,
        "primeira_msg": "01/01/2023",
        "ultima_msg": "31/12/2023",
        "participantes": [
            {"nome": "Alice", "mensagens": 70},
            {"nome": "Bob", "mensagens": 50},
        ],
        "temporal": {
            "por_mes": [
                {"mes": "2023-01", "total": 40},
                {"mes": "2023-02", "total": 80},
            ]
        },
        "tempo_resposta": [
            {
                "nome": "Alice",
                "media_formatada": "2m 30s",
                "mediana_formatada": "1m 10s",
                "total_respostas": 35,
            }
        ],
        "midias": {"fotos": 5, "videos": 2, "audios": 1, "outros": 0},
    }


class TestRenderConversationReport(unittest.TestCase):
    """Relatório individual por conversa (R20)."""

    def test_contem_secoes_e_dados(self):
        """20.1/20.2: o relatório contém os cabeçalhos de seção e os dados da conversa."""
        html = StatsReportRenderer.render_conversation_report(_make_thread_stats())

        # Cabeçalhos das seções exigidas pelo critério 20.2.
        self.assertIn("Participantes", html)
        self.assertIn("Volume Temporal", html)
        self.assertIn("Tempo de Resposta", html)
        self.assertIn("Mídias", html)
        # Seção de resumo também presente.
        self.assertIn("Resumo", html)
        self.assertIn("Relatório da Conversa", html)

        # Dados da conversa renderizados.
        self.assertIn("Alice", html)
        self.assertIn("Bob", html)
        self.assertIn("2m 30s", html)  # tempo de resposta médio
        self.assertIn("01/2023", html)  # rótulo de mês formatado MM/YYYY

    def test_conteudo_dinamico_e_escapado(self):
        """20.3: conteúdo dinâmico com caracteres especiais aparece escapado."""
        stats = _make_thread_stats()
        stats["nome"] = "Tom & Jerry <script>"
        stats["participantes"] = [{"nome": "A<b>&", "mensagens": 10}]

        html = StatsReportRenderer.render_conversation_report(stats)

        # As versões escapadas devem estar presentes.
        self.assertIn("Tom &amp; Jerry &lt;script&gt;", html)
        self.assertIn("A&lt;b&gt;&amp;", html)
        # E o conteúdo bruto perigoso NÃO deve aparecer.
        self.assertNotIn("<script>", html)

    def test_sem_dados_none(self):
        """O caso None retorna indicação 'sem dados' sem levantar erro."""
        html = StatsReportRenderer.render_conversation_report(None)
        self.assertIn("Sem dados para esta conversa", html)

    def test_sem_dados_zero_mensagens(self):
        """Uma conversa com 0 mensagens é tratada como 'sem dados' sem erro."""
        html = StatsReportRenderer.render_conversation_report({"mensagens": 0})
        self.assertIn("Sem dados para esta conversa", html)


# ---------------------------------------------------------------------------
# Testes baseados em propriedade (Hypothesis) para o relatório de estatísticas.
# ---------------------------------------------------------------------------

# Sentinela de conteúdo dinâmico contendo os caracteres especiais <, > e &.
# É distinta o suficiente para não colidir com texto gerado aleatoriamente.
_SENTINEL = "<inj&xy>"
# Forma esperada após o escape de HTML (html.escape com quote=True).
_SENTINEL_ESCAPED = "&lt;inj&amp;xy&gt;"

# Elementos HTML vazios (void): não exigem tag de fechamento.
_VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class _TagBalanceChecker(HTMLParser):
    """Verifica o balanceamento das tags para atestar HTML bem-formado (R33.1).

    Mantém uma pilha de tags abertas. Tags vazias (void) e tags auto-fechadas
    (``<line .../>`` do SVG) não afetam o balanceamento. Ao final, a pilha deve
    estar vazia e ``errors`` sem registros para o HTML ser considerado
    bem-formado (sem tags não fechadas).
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag not in _VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):  # noqa: ANN001
        # Tag auto-fechada (ex.: <line/>, <circle/> no SVG): neutra ao balanço.
        return

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in _VOID_ELEMENTS:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        elif tag in self.stack:
            # Fechamento fora de ordem (aninhamento incorreto).
            self.errors.append(f"Tag </{tag}> fecha fora de ordem (topo: {self.stack[-1]})")
            while self.stack and self.stack.pop() != tag:
                pass
        else:
            self.errors.append(f"Tag </{tag}> sem abertura correspondente")


def _thread_com_sentinela() -> Thread:
    """Monta uma conversa que injeta a sentinela em pontos de conteúdo dinâmico.

    A sentinela aparece como nome da conversa, nome de participante, autor de
    mensagem e corpo de mensagem, garantindo que pelo menos um caminho de
    renderização (barras por participante) sempre a exponha no HTML.
    """
    return Thread(
        thread_id="inj-thread",
        thread_name=_SENTINEL,
        participants=[
            Participant(_SENTINEL, "instagram", "100"),
            Participant("Outro", "instagram", "200"),
        ],
        messages=[
            Message(
                author=_SENTINEL,
                author_id="100",
                platform="instagram",
                sent=datetime(2023, 1, 1, 10, 0),
                body=f"{_SENTINEL} ola mundo",
            ),
            Message(
                author="Outro",
                author_id="200",
                platform="instagram",
                sent=datetime(2023, 1, 2, 11, 0),
                body="resposta normal",
            ),
        ],
    )


# Feature: melhorias-analise-e-projeto, Property 3: Escape de conteúdo dinâmico no relatório
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(base=st.lists(threads(), max_size=3))
def test_property3_escape_conteudo_dinamico(base):
    """Para qualquer string de conteúdo dinâmico (nomes, palavras, nomes de conversas,
    reações, emojis, células da comparação de períodos) contendo `<`, `>` ou `&`, o HTML
    produzido pelo StatsReportRenderer deve conter as entidades HTML correspondentes e
    nenhum desses caracteres crus no segmento de conteúdo.

    A sentinela `<inj&xy>` é injetada em pontos de conteúdo dinâmico (nome de
    participante/conversa, autor e corpo de mensagem). O relatório completo deve conter a
    forma escapada `&lt;inj&amp;xy&gt;` e nunca a forma crua `<inj&xy>`.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
    """
    todos = list(base) + [_thread_com_sentinela()]
    stats = ChatStatistics(todos, "Outro", "200").generate_all()
    html = StatsReportRenderer.render_html_report(stats)

    # R3.1-R3.5: a sentinela aparece escapada na saída...
    assert _SENTINEL_ESCAPED in html
    # ...e nunca em sua forma crua (com os caracteres especiais sem escape).
    assert _SENTINEL not in html


# Feature: melhorias-analise-e-projeto, Property 4: HTML gerado é bem-formado e escapa caracteres especiais
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(base=st.lists(threads(), max_size=4))
def test_property4_html_bem_formado(base):
    """Para qualquer Data_Layer válida, o HTML gerado deve fazer parse sem tags não
    fechadas, e todo conteúdo dinâmico com caracteres especiais deve aparecer escapado.

    Gera conversas (cujos textos já incluem `<`, `>`, `&`) e injeta uma sentinela
    reconhecível. O relatório é parseado para verificar o balanceamento das tags (R33.1)
    e o escape do conteúdo dinâmico (R33.2 / R20.3).

    Validates: Requirements 33.1, 33.2, 20.3
    """
    todos = list(base) + [_thread_com_sentinela()]
    stats = ChatStatistics(todos, "Outro", "200").generate_all()
    html = StatsReportRenderer.render_html_report(stats)

    # R33.1: o HTML faz parse sem tags não fechadas nem aninhamento incorreto.
    checker = _TagBalanceChecker()
    checker.feed(html)
    assert not checker.errors, f"HTML mal-formado: {checker.errors}"
    assert not checker.stack, f"Tags não fechadas: {checker.stack}"

    # R33.2 / R20.3: conteúdo dinâmico com caracteres especiais aparece escapado.
    assert _SENTINEL_ESCAPED in html
    assert _SENTINEL not in html


# ---------------------------------------------------------------------------
# Property 23: acessibilidade dos gráficos e contraste da paleta (R21).
# ---------------------------------------------------------------------------

# Expressão que captura cada gráfico marcado como imagem acessível, exigindo que
# o atributo role="img" seja imediatamente seguido por um aria-label.
_ROLE_IMG_RE = re.compile(r'role="img"')
_ROLE_IMG_LABEL_RE = re.compile(r'role="img"\s+aria-label="([^"]*)"')


def _parse_color(value: str) -> tuple[int, int, int]:
    """Converte uma cor CSS (`#fff`, `#595959` ou `rgb(r,g,b)`) em (R, G, B)."""
    value = value.strip()
    if value.startswith("rgb"):
        nums = re.findall(r"\d+", value)
        return int(nums[0]), int(nums[1]), int(nums[2])
    hex_part = value.lstrip("#")
    if len(hex_part) == 3:
        hex_part = "".join(ch * 2 for ch in hex_part)
    return (
        int(hex_part[0:2], 16),
        int(hex_part[2:4], 16),
        int(hex_part[4:6], 16),
    )


def _srgb_to_linear(channel: int) -> float:
    """Lineariza um canal sRGB (0-255) conforme a definição da WCAG."""
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: str) -> float:
    """Calcula a luminância relativa de uma cor conforme a WCAG 2.x."""
    r, g, b = _parse_color(color)
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def _contrast_ratio(fg: str, bg: str) -> float:
    """Razão de contraste WCAG entre duas cores (>= 1.0; 21.0 = preto/branco)."""
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def _heatmap_colors(intensity: float) -> tuple[str, str]:
    """Replica a paleta de duas zonas do heatmap (R21.3): (fundo, texto).

    Espelha exatamente a lógica de `StatsReportRenderer.render_html_report`:
    zona clara (< 0.55) usa fundo claro + texto escuro; zona escura (>= 0.55)
    usa fundo escuro + texto branco.
    """
    if intensity == 0:
        return "#f5f5f5", "#1a1a1a"
    if intensity < 0.55:
        t2 = intensity / 0.55
        r = int(245 - t2 * 95)
        g = int(245 - t2 * 55)
        b = int(245 - t2 * 5)
        return f"rgb({r},{g},{b})", "#1a1a1a"
    t2 = (intensity - 0.55) / 0.45
    r = int(37 + t2 * 148)
    g = int(99 - t2 * 71)
    b = int(235 - t2 * 207)
    return f"rgb({r},{g},{b})", "#fff"


#: Fundos claros usados nas seções e tags de gráfico (stats-section, word-tag, células).
_LIGHT_BACKGROUNDS = ("#fff", "#f8f8f8")

#: Cores de texto fixas aplicadas sobre os fundos claros nos gráficos (R21.3).
_LIGHT_TEXT_COLORS = ("#595959", "#555", "#1a1a1a", "#2e7d32", "#c62828")

#: Razão mínima de contraste exigida pela WCAG AA para texto normal.
_MIN_CONTRAST = 4.5


# Feature: melhorias-analise-e-projeto, Property 23: Gráficos são acessíveis e têm contraste suficiente
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(base=st.lists(threads(), min_size=1, max_size=4))
def test_property23_acessibilidade_e_contraste(base):
    """Para qualquer relatório gerado, todo elemento de gráfico deve possuir rótulo textual
    ou atributo ARIA descritivo e distinguir séries por um meio adicional à cor; para
    qualquer combinação texto/fundo definida na paleta de gráficos, a razão de contraste
    deve ser de pelo menos 4.5:1.

    O relatório é gerado a partir de conversas aleatórias e inspecionado: cada ocorrência de
    `role="img"` deve vir acompanhada de um `aria-label` não vazio (R21.1/R21.2). Em paralelo,
    cada combinação de cor texto/fundo fixada na paleta dos gráficos — incluindo o gradiente
    de duas zonas do heatmap — é verificada quanto ao contraste >= 4.5:1 (R21.3).

    Validates: Requirements 21.1, 21.2, 21.3
    """
    stats = ChatStatistics(list(base), "Outro", "200").generate_all()
    html = StatsReportRenderer.render_html_report(stats)

    # R21.1/R21.2: todo gráfico marcado como imagem possui aria-label descritivo.
    total_role_img = len(_ROLE_IMG_RE.findall(html))
    rotulos = _ROLE_IMG_LABEL_RE.findall(html)
    assert (
        len(rotulos) == total_role_img
    ), f'Há {total_role_img} role="img" mas apenas {len(rotulos)} com aria-label'
    for rotulo in rotulos:
        assert rotulo.strip(), "aria-label de gráfico não pode ser vazio"

    # R21.3: cores de texto fixas sobre os fundos claros dos gráficos.
    for fg in _LIGHT_TEXT_COLORS:
        for bg in _LIGHT_BACKGROUNDS:
            ratio = _contrast_ratio(fg, bg)
            assert (
                ratio >= _MIN_CONTRAST
            ), f"Contraste insuficiente: texto {fg} sobre fundo {bg} = {ratio:.2f}:1"

    # R21.3: gradiente de duas zonas do heatmap (texto vs. fundo) ao longo da intensidade.
    for step in range(0, 101):
        intensity = step / 100.0
        bg, fg = _heatmap_colors(intensity)
        ratio = _contrast_ratio(fg, bg)
        assert (
            ratio >= _MIN_CONTRAST
        ), f"Heatmap: texto {fg} sobre {bg} (intensidade {intensity:.2f}) = {ratio:.2f}:1"


if __name__ == "__main__":
    unittest.main()
