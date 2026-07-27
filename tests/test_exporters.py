"""
Testes para o módulo exporters.py - Exportadores JSON e CSV
"""

import csv
import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.advanced_stats_schema import (
    ADVANCED_STATS_BY_SOURCE_KEY,
    ADVANCED_STATS_FAMILIES,
    build_advanced_section,
)
from meta_chat_exporter.exporters import CSVExporter, JSONExporter
from meta_chat_exporter.models import Attachment, Message, Participant, Thread
from tests import strategies as gen


def _make_msg(
    author="user1",
    body="Hello",
    sent=None,
    attachments=None,
    is_call=False,
    call_type="",
    call_duration=0,
    call_missed=False,
    disappearing=False,
    share_url=None,
    share_text=None,
    removed_by_sender=False,
):
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
        share_text=share_text,
        is_call=is_call,
        call_type=call_type,
        call_duration=call_duration,
        call_missed=call_missed,
        removed_by_sender=removed_by_sender,
        source_file="test.html",
    )


def _make_thread(thread_id="1", name="Test Chat", participants=None, messages=None):
    return Thread(
        thread_id=thread_id,
        thread_name=name,
        participants=participants
        or [Participant("user1", "instagram", "100"), Participant("user2", "instagram", "200")],
        messages=messages or [],
    )


class TestJSONExporter(unittest.TestCase):
    """Testes para exportação JSON"""

    def setUp(self):
        self.output_path = Path(__file__).parent / "test_output.json"

    def tearDown(self):
        if self.output_path.exists():
            self.output_path.unlink()

    def test_export_basic(self):
        msgs = [_make_msg(body="Hello"), _make_msg(author="user2", body="Hi")]
        thread = _make_thread(messages=msgs)
        exporter = JSONExporter([thread], "user1", "100")
        exporter.export(self.output_path, include_stats=False)

        self.assertTrue(self.output_path.exists())
        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("meta", data)
        self.assertIn("conversas", data)
        self.assertEqual(data["meta"]["total_conversas"], 1)
        self.assertEqual(data["meta"]["total_mensagens"], 2)
        self.assertEqual(data["meta"]["owner_username"], "user1")

    def test_export_with_stats(self):
        msgs = [_make_msg(body="Hello"), _make_msg(author="user2", body="Hi")]
        thread = _make_thread(messages=msgs)
        exporter = JSONExporter([thread], "user1", "100")
        exporter.export(self.output_path, include_stats=True)

        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("estatisticas", data)
        self.assertIn("resumo", data["estatisticas"])

    def test_export_message_fields(self):
        msg = _make_msg(
            body="Test message", share_url="https://example.com", share_text="Cool link"
        )
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertEqual(conv_msg["corpo"], "Test message")
        self.assertEqual(conv_msg["link_compartilhado"], "https://example.com")

    def test_export_call_message(self):
        msg = _make_msg(is_call=True, call_type="Video", call_duration=120, call_missed=False)
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertIn("chamada", conv_msg)
        self.assertEqual(conv_msg["chamada"]["tipo"], "Video")
        self.assertEqual(conv_msg["chamada"]["duracao"], 120)

    def test_export_disappearing_message(self):
        msg = _make_msg(disappearing=True)
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertTrue(conv_msg["temporaria"])

    def test_export_attachment(self):
        att = Attachment(filename="photo.jpg", file_type="image/jpeg")
        msg = _make_msg(attachments=[att])
        thread = _make_thread(messages=[msg])
        exporter = JSONExporter([thread])
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)

        conv_msg = data["conversas"][0]["mensagens"][0]
        self.assertIn("anexos", conv_msg)
        self.assertEqual(conv_msg["anexos"][0]["filename"], "photo.jpg")

    def test_export_empty_threads(self):
        exporter = JSONExporter([], "user1", "100")
        exporter.export(self.output_path, include_stats=False)

        with open(self.output_path, encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["meta"]["total_conversas"], 0)
        self.assertEqual(data["conversas"], [])


class TestCSVExporter(unittest.TestCase):
    """Testes para exportação CSV"""

    def setUp(self):
        self.output_path = Path(__file__).parent / "test_output.csv"
        self.stats_path = Path(__file__).parent / "test_output_stats.csv"

    def tearDown(self):
        for p in [self.output_path, self.stats_path]:
            if p.exists():
                p.unlink()

    def test_export_basic(self):
        msgs = [_make_msg(body="Hello"), _make_msg(author="user2", body="Hi")]
        thread = _make_thread(messages=msgs)
        exporter = CSVExporter([thread], "user1", "100")
        exporter.export(self.output_path)

        self.assertTrue(self.output_path.exists())
        with open(self.output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["autor"], "user1")
        self.assertEqual(rows[0]["corpo"], "Hello")

    def test_csv_fields(self):
        msg = _make_msg(
            disappearing=True, share_url="https://ex.com", is_call=True, call_type="Audio"
        )
        thread = _make_thread(messages=[msg])
        exporter = CSVExporter([thread])
        exporter.export(self.output_path)

        with open(self.output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        self.assertEqual(row["temporaria"], "Sim")
        self.assertEqual(row["eh_chamada"], "Sim")
        self.assertEqual(row["tipo_chamada"], "Audio")
        self.assertEqual(row["link_compartilhado"], "https://ex.com")

    def test_export_stats(self):
        msgs = [_make_msg(), _make_msg(author="user2")]
        thread = _make_thread(messages=msgs)
        exporter = CSVExporter([thread], "user1", "100")
        exporter.export(self.output_path)
        exporter.export_stats(self.stats_path)

        self.assertTrue(self.stats_path.exists())

    def test_multiple_threads(self):
        t1 = _make_thread(thread_id="1", messages=[_make_msg(body="A")])
        t2 = _make_thread(thread_id="2", name="Chat 2", messages=[_make_msg(body="B")])
        exporter = CSVExporter([t1, t2])
        exporter.export(self.output_path)

        with open(self.output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.assertEqual(len(rows), 2)
        thread_ids = {r["conversa_id"] for r in rows}
        self.assertEqual(thread_ids, {"1", "2"})

    def test_attachment_in_csv(self):
        att = Attachment(filename="voice.m4a", file_type="audio/mp4")
        msg = _make_msg(attachments=[att])
        thread = _make_thread(messages=[msg])
        exporter = CSVExporter([thread])
        exporter.export(self.output_path)

        with open(self.output_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            row = next(reader)

        self.assertEqual(row["anexos"], "voice.m4a")
        self.assertEqual(row["tipos_anexo"], "audio/mp4")


class TestCSVAdvancedStatsFlatten(unittest.TestCase):
    """Testes do achatamento de famílias avançadas para CSV (R29.2)"""

    def test_top_level_list_one_row_per_item(self):
        from meta_chat_exporter.exporters import _flatten_advanced_family

        data = [
            {"thread_id": "1", "indice_msgs": 0.5, "indice_chars": 0.4},
            {"thread_id": "2", "indice_msgs": 1.0, "indice_chars": 1.0},
        ]
        campos = ("thread_id", "indice_msgs", "indice_chars")
        rows = _flatten_advanced_family(data, campos)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {"thread_id": "1", "indice_msgs": 0.5, "indice_chars": 0.4})

    def test_dict_with_list_container_merges_scalars(self):
        from meta_chat_exporter.exporters import _flatten_advanced_family

        data = {"total": 3, "por_autor": [{"nome": "a", "total": 2}, {"nome": "b", "total": 1}]}
        campos = ("total", "por_autor", "nome")
        rows = _flatten_advanced_family(data, campos)

        self.assertEqual(len(rows), 2)
        # O total por autor sobrepõe o total do topo na expansão
        self.assertEqual(rows[0]["nome"], "a")
        self.assertEqual(rows[0]["total"], 2)
        # Colunas declaradas no esquema sempre presentes
        for row in rows:
            self.assertEqual(set(row.keys()), set(campos))

    def test_dict_periodo_uses_extra_columns(self):
        from meta_chat_exporter.exporters import _flatten_advanced_family

        data = {"total": 7, "por_periodo": {"2024-01": 5, "2024-02": 2}}
        campos = ("total", "por_periodo", "periodo", "contagem")
        rows = _flatten_advanced_family(data, campos)

        self.assertEqual(len(rows), 2)
        periodos = {r["periodo"]: r["contagem"] for r in rows}
        self.assertEqual(periodos, {"2024-01": 5, "2024-02": 2})
        self.assertEqual(rows[0]["total"], 7)

    def test_multiple_containers_marks_origin(self):
        from meta_chat_exporter.exporters import _flatten_advanced_family

        data = {
            "bigramas": [{"ngrama": "oi tudo", "contagem": 2}],
            "trigramas": [{"ngrama": "oi tudo bem", "contagem": 1}],
        }
        campos = ("bigramas", "trigramas", "ngrama", "contagem")
        rows = _flatten_advanced_family(data, campos)

        self.assertEqual(len(rows), 2)
        # Cada linha guarda sua origem na coluna homônima para desambiguar
        origem = {(r["bigramas"], r["trigramas"]) for r in rows}
        self.assertEqual(origem, {("bigramas", ""), ("", "trigramas")})

    def test_nested_structure_serialized_as_json(self):
        from meta_chat_exporter.exporters import _flatten_advanced_family

        data = [{"nome": "a", "distribuicao_horaria": {"0": 1, "23": 4}}]
        campos = ("nome", "distribuicao_horaria")
        rows = _flatten_advanced_family(data, campos)

        self.assertEqual(rows[0]["nome"], "a")
        self.assertEqual(json.loads(rows[0]["distribuicao_horaria"]), {"0": 1, "23": 4})


class TestCSVExporterAdvancedStats(unittest.TestCase):
    """Testes de export_advanced_stats (R29.2/R29.3)"""

    def setUp(self):
        self.base_path = Path(__file__).parent / "test_output_adv.csv"

    def tearDown(self):
        for p in self.base_path.parent.glob("test_output_adv*"):
            p.unlink()

    def test_creates_one_file_per_present_family_with_schema_headers(self):
        from unittest.mock import patch

        fake_stats = {
            "resumo": {"x": 1},
            "editadas": {"total": 3, "por_autor": [{"nome": "a", "total": 2}]},
            "dominios": {"total": 2, "por_dominio": [{"dominio": "ex.com", "contagem": 2}]},
        }
        thread = _make_thread(messages=[_make_msg()])
        exporter = CSVExporter([thread], "user1", "100")

        with patch("meta_chat_exporter.exporters.ChatStatistics") as mock_stats:
            mock_stats.return_value.generate_all.return_value = fake_stats
            written = exporter.export_advanced_stats(self.base_path)

        json_keys = {p.name for p in written}
        self.assertIn("test_output_adv_editadas.csv", json_keys)
        self.assertIn("test_output_adv_dominios.csv", json_keys)
        # Famílias ausentes não geram arquivo
        self.assertEqual(len(written), 2)

        # Cabeçalhos do CSV devem ser exatamente os campos do esquema (consistência JSON/CSV)
        for path in written:
            source_key = path.stem.replace("test_output_adv_", "")
            family = ADVANCED_STATS_BY_SOURCE_KEY[source_key]
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                self.assertEqual(tuple(reader.fieldnames), family.campos)

    def test_no_advanced_families_writes_no_files(self):
        from unittest.mock import patch

        thread = _make_thread(messages=[_make_msg()])
        exporter = CSVExporter([thread])

        with patch("meta_chat_exporter.exporters.ChatStatistics") as mock_stats:
            mock_stats.return_value.generate_all.return_value = {"resumo": {}}
            written = exporter.export_advanced_stats(self.base_path)

        self.assertEqual(written, [])


class TestAdvancedStatsSchema(unittest.TestCase):
    """Testes para o esquema compartilhado de métricas avançadas (R29.1/R29.3)"""

    def test_source_keys_are_unique(self):
        keys = [fam.source_key for fam in ADVANCED_STATS_FAMILIES]
        self.assertEqual(len(keys), len(set(keys)))

    def test_index_matches_families(self):
        self.assertEqual(len(ADVANCED_STATS_BY_SOURCE_KEY), len(ADVANCED_STATS_FAMILIES))
        for fam in ADVANCED_STATS_FAMILIES:
            self.assertIs(ADVANCED_STATS_BY_SOURCE_KEY[fam.source_key], fam)

    def test_build_advanced_section_pulls_present_families(self):
        stats = {
            "resumo": {"x": 1},
            "editadas": {"total": 3, "por_autor": [{"nome": "a", "total": 3}]},
            "dominios": {"total": 1, "por_dominio": [{"dominio": "ex.com", "contagem": 1}]},
        }
        avancadas = build_advanced_section(stats)
        self.assertIn("editadas", avancadas)
        self.assertIn("dominios", avancadas)
        # Chaves não-avançadas não vazam para a seção
        self.assertNotIn("resumo", avancadas)
        self.assertEqual(avancadas["editadas"], stats["editadas"])

    def test_build_advanced_section_omits_missing_families(self):
        # Famílias ainda não implementadas simplesmente não aparecem (sem erro)
        avancadas = build_advanced_section({"resumo": {}})
        self.assertEqual(avancadas, {})

    def test_build_advanced_section_omits_none_values(self):
        avancadas = build_advanced_section({"editadas": None})
        self.assertNotIn("editadas", avancadas)

    def test_investigation_metrics_a1_a2_a4_in_schema(self):
        keys = {fam.source_key for fam in ADVANCED_STATS_FAMILIES}
        self.assertIn("timeline_contatos", keys)
        self.assertIn("atividade_noturna", keys)
        self.assertIn("taxa_resposta", keys)
        stats = {
            "timeline_contatos": [
                {
                    "nome": "bob",
                    "primeira_msg": "01/01/2024 10:00",
                    "ultima_msg": "02/01/2024 11:00",
                    "total_mensagens": 2,
                }
            ],
            "atividade_noturna": {
                "total_noturna": 1,
                "por_autor": [{"nome": "bob", "mensagens": 1}],
            },
            "taxa_resposta": [
                {
                    "nome": "bob",
                    "msgs_alvo": 1,
                    "msgs_contato": 1,
                    "respostas_alvo": 1,
                    "respostas_contato": 1,
                    "taxa_resposta_alvo": 100.0,
                    "taxa_resposta_contato": 100.0,
                }
            ],
        }
        avancadas = build_advanced_section(stats)
        self.assertIn("timeline_contatos", avancadas)
        self.assertIn("atividade_noturna", avancadas)
        self.assertIn("taxa_resposta", avancadas)


class TestJSONExporterAdvancedStats(unittest.TestCase):
    """Testes para a seção estatisticas.avancadas no JSON (R29.1)"""

    def setUp(self):
        self.output_path = Path(__file__).parent / "test_output_adv.json"

    def tearDown(self):
        if self.output_path.exists():
            self.output_path.unlink()

    def _load(self):
        with open(self.output_path, encoding="utf-8") as f:
            return json.load(f)

    def test_avancadas_present_with_stats(self):
        msgs = [_make_msg(body="Hello"), _make_msg(author="user2", body="Hi")]
        thread = _make_thread(messages=msgs)
        exporter = JSONExporter([thread], "user1", "100")
        exporter.export(self.output_path, include_stats=True)

        data = self._load()
        self.assertIn("estatisticas", data)
        self.assertIn("avancadas", data["estatisticas"])
        # Toda chave da seção avancadas deve ser uma família declarada no esquema
        declared = {fam.json_key for fam in ADVANCED_STATS_FAMILIES}
        for key in data["estatisticas"]["avancadas"]:
            self.assertIn(key, declared)

    def test_avancadas_absent_without_stats(self):
        thread = _make_thread(messages=[_make_msg()])
        exporter = JSONExporter([thread], "user1", "100")
        exporter.export(self.output_path, include_stats=False)

        data = self._load()
        self.assertNotIn("estatisticas", data)


# ---------------------------------------------------------------------------
# Teste de propriedade — consistência de esquema JSON/CSV (Property 21)
# ---------------------------------------------------------------------------

# Campos que NÃO devem mais aparecer em nenhuma família (regressão do grafo:
# a família passou a expor estrutura `nodes`/`edges` em vez de SVG/contagens).
_CAMPOS_PROIBIDOS = frozenset({"svg", "total_nos", "total_conexoes"})


def _collect_json_field_names(value) -> set[str]:
    """Coleta os nomes de campos *estruturais* de uma família na seção JSON.

    Espelha exatamente o achatamento usado pela exportação CSV
    (``_flatten_advanced_family``): um nível de expansão de contêineres-lista.
    Chaves de mapeamentos dinâmicos (ex.: ``por_periodo`` = {período: contagem}
    ou ``distribuicao_horaria``) são *valores*, não campos de esquema, e por isso
    não são coletadas. Assim, os nomes coletados devem ser um subconjunto dos
    ``campos`` declarados no esquema compartilhado.
    """
    names: set[str] = set()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                names |= set(item.keys())
    elif isinstance(value, dict):
        for key, val in value.items():
            names.add(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        names |= set(item.keys())
    return names


# Feature: melhorias-analise-e-projeto, Property 21: Exportações avançadas usam nomes de campos consistentes
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(threads=st.lists(gen.threads(), max_size=4))
def test_exportacoes_avancadas_usam_nomes_de_campos_consistentes(threads: list[Thread]) -> None:
    """Property 21 — JSON e CSV usam os MESMOS nomes de campos do esquema.

    Para qualquer conjunto de threads, a seção ``estatisticas.avancadas`` do JSON
    e a exportação ``export_advanced_stats`` do CSV devem desenhar os nomes de
    campos exclusivamente do esquema compartilhado ``ADVANCED_STATS_FAMILIES``:

    - cada família presente aparece sob seu ``json_key`` declarado;
    - os nomes de campos usados por ambos os formatos pertencem aos ``campos``
      daquela família (sem campos espúrios como ``svg``/``total_nos``/``total_conexoes``);
    - as MESMAS famílias estão presentes/ausentes em ambos os formatos (omissão
      defensiva consistente, sem erro);
    - a família ``grafo`` expõe estrutura ``nodes``/``edges`` (nunca ``svg``).

    **Validates: Requirements 29.1, 29.2, 29.3**
    """
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # --- Exportação JSON (seção estatisticas.avancadas) ------------------
        json_path = tmp_path / "export.json"
        JSONExporter(threads, "user1", "100").export(json_path, include_stats=True)
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        avancadas = data.get("estatisticas", {}).get("avancadas", {})

        # --- Exportação CSV (um arquivo por família) -------------------------
        csv_base = tmp_path / "export.csv"
        written = CSVExporter(threads, "user1", "100").export_advanced_stats(csv_base)

        # Mapear cada CSV escrito para sua família e ler os cabeçalhos.
        declared_json_keys = {fam.json_key for fam in ADVANCED_STATS_FAMILIES}
        csv_json_keys: set[str] = set()
        csv_headers_por_familia: dict[str, tuple[str, ...]] = {}
        for path in written:
            source_key = path.stem.replace("export_", "", 1)
            family = ADVANCED_STATS_BY_SOURCE_KEY[source_key]
            csv_json_keys.add(family.json_key)
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = tuple(reader.fieldnames or ())
            csv_headers_por_familia[family.json_key] = headers

            # CSV usa EXATAMENTE os campos do esquema como cabeçalhos.
            assert headers == family.campos, (
                f"CSV da família '{family.json_key}' usa cabeçalhos {headers}, "
                f"esperado {family.campos}"
            )
            # Nenhum campo proibido (regressão svg/total_nos/total_conexoes).
            assert _CAMPOS_PROIBIDOS.isdisjoint(
                headers
            ), f"CSV da família '{family.json_key}' expõe campo proibido: {headers}"

        # 1) Toda chave do JSON é uma família declarada no esquema.
        for json_key in avancadas:
            assert (
                json_key in declared_json_keys
            ), f"Chave '{json_key}' em estatisticas.avancadas não está no esquema"

        # 2) JSON e CSV incluem/omitem EXATAMENTE as mesmas famílias.
        assert (
            set(avancadas) == csv_json_keys
        ), f"Famílias divergem entre JSON {set(avancadas)} e CSV {csv_json_keys}"

        # 3) Os nomes de campos do JSON pertencem aos campos do esquema da família
        #    (mesmos nomes que o CSV usa), sem campos espúrios.
        by_json_key = {fam.json_key: fam for fam in ADVANCED_STATS_FAMILIES}
        for json_key, valor in avancadas.items():
            family = by_json_key[json_key]
            json_fields = _collect_json_field_names(valor)
            assert json_fields <= set(family.campos), (
                f"JSON da família '{json_key}' usa campos {json_fields - set(family.campos)} "
                f"fora do esquema {family.campos}"
            )
            assert _CAMPOS_PROIBIDOS.isdisjoint(
                json_fields
            ), f"JSON da família '{json_key}' expõe campo proibido: {json_fields}"

        # 4) A família grafo expõe estrutura nodes/edges, nunca svg.
        if "grafo" in avancadas:
            grafo = avancadas["grafo"]
            assert isinstance(grafo, dict)
            assert "nodes" in grafo and "edges" in grafo
            assert "svg" not in grafo
            assert set(grafo) <= set(by_json_key["grafo"].campos)
            # E o CSV correspondente herda os mesmos cabeçalhos do esquema.
            assert csv_headers_por_familia["grafo"] == by_json_key["grafo"].campos


if __name__ == "__main__":
    unittest.main()
