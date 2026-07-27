"""
Teste de propriedade para a redação consistente em todos os formatos (R4).

Property 5: aplicar a redação **uma única vez** na Data_Layer deve garantir que
nenhuma saída (HTML unificado, HTML individual, JSON, CSV e relatório de
estatísticas) contenha os nomes de usuários originais nem as sequências de 8 ou
mais dígitos originais — incluindo os caminhos de anexos exibidos na seção de
integridade (R4.6).

Estratégia: às threads geradas livremente (cobrindo casos de borda) é anexada
uma thread "sentinela" com dados sensíveis reconhecíveis e improváveis de serem
reconstruídos por acaso:
- nome de autor/participante: "SensitiveUser12345678";
- corpo de mensagem com o número longo "12345678901";
- anexo com o número longo "87654321" embutido no nome do arquivo.

A redação é aplicada uma vez sobre uma cópia profunda da Data_Layer; em seguida
cada formato é exportado e o texto resultante é inspecionado. As asserções
recaem sobre esses sentinelas específicos (em campos cobertos pela redação:
nomes, corpo, nome de conversa e nomes de anexos), evitando falsos positivos por
reconstrução acidental.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Permitir importar os módulos planos do projeto a partir de tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.exporters import CSVExporter, JSONExporter  # noqa: E402
from meta_chat_exporter.generators_all import AllChatsHTMLGenerator  # noqa: E402
from meta_chat_exporter.generators_single import ChatHTMLGenerator  # noqa: E402
from meta_chat_exporter.models import Attachment, Message, Participant, Thread  # noqa: E402
from meta_chat_exporter.redaction import RedactionEngine  # noqa: E402
from meta_chat_exporter.stats import ChatStatistics  # noqa: E402
from tests import strategies as gen  # noqa: E402

# Dono da exportação (não deve colidir com o nome sentinela).
OWNER = "DonoDaExportacao"

# Sentinelas sensíveis injetados em campos cobertos pela redação.
SENTINEL_NAME = "SensitiveUser12345678"
SENTINEL_BODY_NUMBER = "12345678901"  # número longo (11 dígitos) no corpo
SENTINEL_FILE_NUMBER = "87654321"  # número longo (8 dígitos) no nome do anexo

# Conjunto de strings que NÃO podem aparecer em nenhuma saída redigida.
SENTINELS = (SENTINEL_NAME, SENTINEL_BODY_NUMBER, SENTINEL_FILE_NUMBER)


def _make_sentinel_thread() -> Thread:
    """Constrói uma thread com dados sensíveis reconhecíveis."""
    return Thread(
        thread_id="sentinel-thread",  # id não-sensível (não é alvo de redação)
        thread_name="Conversa Secreta",
        participants=[Participant(SENTINEL_NAME, "instagram", "99887766554433")],
        past_participants=[Participant(SENTINEL_NAME, "instagram", "99887766554433")],
        messages=[
            Message(
                author=SENTINEL_NAME,
                author_id="99887766554433",
                platform="instagram",
                sent=datetime(2022, 5, 1, 12, 0, 0),
                body=f"meu telefone e {SENTINEL_BODY_NUMBER} ligue agora",
                attachments=[
                    Attachment(
                        filename=f"IMG_{SENTINEL_FILE_NUMBER}.jpg",
                        file_type="image",
                        local_path=f"media/IMG_{SENTINEL_FILE_NUMBER}.jpg",
                    )
                ],
            )
        ],
    )


def _assert_no_sentinels(label: str, text: str) -> None:
    """Falha se qualquer sentinela sensível original aparecer no texto."""
    for sentinel in SENTINELS:
        assert sentinel not in text, f"Dado sensível '{sentinel}' vazou na saída de {label}"


# Feature: melhorias-analise-e-projeto, Property 5: Redação remove dados sensíveis em todos os formatos
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(extra_threads=st.lists(gen.threads(), max_size=2))
def test_redacao_remove_dados_sensiveis_em_todos_os_formatos(extra_threads: list[Thread]) -> None:
    """Property 5 — após uma única redação, nenhum formato expõe os sentinelas.

    **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6**
    """
    # Data_Layer = threads geradas + thread sentinela com dados sensíveis.
    threads = [*extra_threads, _make_sentinel_thread()]

    # R4.1 — redação aplicada UMA ÚNICA vez sobre uma cópia profunda.
    redacted = deepcopy(threads)
    RedactionEngine(OWNER).redact(redacted)

    # Localiza a thread sentinela já redigida (para o HTML individual).
    sentinel_redacted = next(t for t in redacted if t.thread_id == "sentinel-thread")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # R4.2 — JSON
        json_path = JSONExporter(redacted, OWNER, "").export(
            tmp_path / "saida.json", include_stats=False
        )
        json_text = json_path.read_text(encoding="utf-8")
        # Garante que o JSON é válido e os sentinelas não estão presentes.
        json.loads(json_text)
        _assert_no_sentinels("JSON", json_text)

        # R4.3 — CSV
        csv_path = CSVExporter(redacted, OWNER, "").export(tmp_path / "saida.csv")
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        _assert_no_sentinels("CSV", csv_text)

    # R4.4 / R4.6 — HTML unificado (já redigido na origem) e HTML individual.
    unified_html = AllChatsHTMLGenerator(
        redacted, OWNER, "", redact=True, already_redacted=True
    ).generate()
    _assert_no_sentinels("HTML unificado", unified_html)

    single_html = ChatHTMLGenerator(sentinel_redacted, OWNER, "").generate()
    _assert_no_sentinels("HTML individual", single_html)

    # R4.5 — Relatório de estatísticas.
    stats_html = ChatStatistics(redacted, OWNER, "").generate_html_report()
    _assert_no_sentinels("relatório de estatísticas", stats_html)
