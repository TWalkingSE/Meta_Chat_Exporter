"""
Meta Platforms Chat Exporter - Estatísticas e Analytics
Gera estatísticas detalhadas sobre as conversas exportadas
"""

import logging
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from langdetect import DetectorFactory, detect_langs
    from langdetect.lang_detect_exception import LangDetectException

    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    detect_langs = None
    LANGDETECT_AVAILABLE = False

    class LangDetectException(Exception):  # type: ignore[no-redef]
        """Fallback local quando langdetect não está instalado."""


try:
    # Biblioteca opcional de emojis (R24.2): cobertura Unicode mais ampla que o
    # regex interno. Não é dependência obrigatória; detectamos a disponibilidade
    # em tempo de import para permitir degradação graciosa (R24.3).
    import emoji as emoji_lib

    EMOJI_AVAILABLE = True
except ImportError:
    emoji_lib = None
    EMOJI_AVAILABLE = False


from meta_chat_exporter.config import config
from meta_chat_exporter.i18n import (
    get_lang_code_map,
    get_lang_keywords,
    get_stop_words,
    get_weekday_names,
)
from meta_chat_exporter.models import Message, Thread
from meta_chat_exporter.stats_investigation import (
    stats_atividade_noturna,
    stats_dominancia_grupo,
    stats_iniciadores,
    stats_midia_por_contato,
    stats_rajadas,
    stats_removidas_por_autor,
    stats_taxa_resposta,
    stats_timeline_contatos,
    stats_timeline_links,
    stats_velocidade_conversa,
)
from meta_chat_exporter.stats_report import StatsReportRenderer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatsFilter:
    """Filtro do painel de estatísticas por conversa e/ou intervalo de datas (R19).

    Define o contrato de filtragem usado para recalcular as métricas sobre um
    subconjunto das mensagens:

    - ``thread_id``: quando informado, restringe a análise às mensagens da
      conversa correspondente (R19.1).
    - ``data_inicio`` / ``data_fim``: limites *inclusivos* sobre ``Message.sent``
      que restringem a análise às mensagens dentro do intervalo (R19.2).

    Quando todos os campos são ``None`` o filtro é considerado vazio e a análise
    abrange o conjunto global (R19.3).
    """

    thread_id: str | None = None
    data_inicio: datetime | None = None
    data_fim: datetime | None = None

    def is_empty(self) -> bool:
        """True quando nenhum critério está definido (análise global, R19.3)."""
        return self.thread_id is None and self.data_inicio is None and self.data_fim is None

    def match_thread(self, thread: Thread) -> bool:
        """Indica se a conversa satisfaz o critério de ``thread_id`` (R19.1)."""
        return self.thread_id is None or thread.thread_id == self.thread_id

    def match_message(self, message: Message) -> bool:
        """Indica se a mensagem satisfaz o critério de intervalo de datas (R19.2).

        Mensagens sem data (``sent`` ausente) são excluídas quando há qualquer
        limite de intervalo, pois não é possível posicioná-las no tempo.
        """
        if self.data_inicio is None and self.data_fim is None:
            return True
        if message.sent is None:
            return False
        if self.data_inicio is not None and message.sent < self.data_inicio:
            return False
        if self.data_fim is not None and message.sent > self.data_fim:
            return False
        return True

    @classmethod
    def coerce(cls, filtro: "StatsFilter | dict[str, Any] | None") -> "StatsFilter":
        """Normaliza um filtro recebido como ``StatsFilter``, ``dict`` ou ``None``."""
        if filtro is None:
            return cls()
        if isinstance(filtro, StatsFilter):
            return filtro
        return cls(
            thread_id=filtro.get("thread_id"),
            data_inicio=filtro.get("data_inicio"),
            data_fim=filtro.get("data_fim"),
        )


def _novo_participante() -> dict[str, int]:
    """Fábrica do registro de contadores por participante (R25).

    Replica exatamente o ``defaultdict`` antes embutido em
    ``_stats_por_participante``, garantindo que a passagem única produza os
    mesmos campos e zeros iniciais da implementação multi-passagem.
    """
    return {
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


@dataclass
class _PassAccumulators:
    """Acumuladores compartilhados preenchidos numa única passagem (R25.1).

    Reúne todas as agregações que dependem de iteração por mensagem. Cada campo
    corresponde a um estado intermediário que antes era reconstruído por um
    ``_stats_*`` independente; agora todos são alimentados de uma só vez por
    ``ChatStatistics._single_pass_accumulate`` e consumidos pelos métodos
    derivados, preservando exatamente o mesmo contrato de saída (R25.2).
    """

    # Total bruto de mensagens analisadas.
    total_msgs: int = 0

    # Resumo geral: datas-limite e contadores por flag.
    primeira_data: datetime | None = None
    ultima_data: datetime | None = None
    total_attachments: int = 0
    total_calls: int = 0
    total_disappearing: int = 0
    total_removed: int = 0
    total_shares: int = 0
    total_reactions: int = 0
    total_payments: int = 0
    total_subscriptions: int = 0

    # Estatísticas por participante.
    participant_stats: defaultdict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(_novo_participante)
    )

    # Agregações temporais (mês/dia da semana/ano).
    temporal_por_mes: Counter[str] = field(default_factory=Counter)
    temporal_por_dia_semana: Counter[int] = field(default_factory=Counter)
    temporal_por_ano: Counter[int] = field(default_factory=Counter)

    # Mídias (ordem de teste distinta de por_participante).
    midias_fotos: int = 0
    midias_videos: int = 0
    midias_audios: int = 0
    midias_outros: int = 0

    # Chamadas.
    chamadas_total: int = 0
    chamadas_perdidas: int = 0
    chamadas_duracao_total: int = 0
    chamadas_tipos: Counter[str] = field(default_factory=Counter)

    # Palavras.
    palavras_counter: Counter[str] = field(default_factory=Counter)
    palavras_total: int = 0

    # Horários e heatmap.
    horarios_por_hora: Counter[int] = field(default_factory=Counter)
    heatmap_matrix: list[list[int]] = field(default_factory=lambda: [[0] * 24 for _ in range(7)])

    # Reações por autor.
    reacoes_por_autor: Counter[str] = field(default_factory=Counter)

    # Emojis.
    emoji_counter: Counter[str] = field(default_factory=Counter)
    emoji_by_author: defaultdict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    emoji_msgs_com_emoji: int = 0

    # Editadas.
    editadas_total: int = 0
    editadas_por_autor: Counter[str] = field(default_factory=Counter)

    # Agregações temporais por período mensal.
    pagamentos_por_periodo: Counter[str] = field(default_factory=Counter)
    eventos_por_periodo: Counter[str] = field(default_factory=Counter)
    removidas_por_periodo: Counter[str] = field(default_factory=Counter)
    temporarias_por_periodo: Counter[str] = field(default_factory=Counter)

    # Domínios de links.
    dominios_por_dominio: Counter[str] = field(default_factory=Counter)

    # Tamanho de mensagens.
    tamanho_dist_geral: Counter[str] = field(default_factory=Counter)
    tamanho_dist_por_autor: defaultdict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    tamanho_total_chars: int = 0
    tamanho_total_msgs_com_texto: int = 0

    # N-gramas.
    ngramas_bigramas: Counter[str] = field(default_factory=Counter)
    ngramas_trigramas: Counter[str] = field(default_factory=Counter)

    # Métricas linguísticas por participante.
    ling_perguntas: Counter[str] = field(default_factory=Counter)
    ling_afirmacoes: Counter[str] = field(default_factory=Counter)
    ling_tokens_total: Counter[str] = field(default_factory=Counter)
    ling_tokens_unicos: defaultdict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    ling_distrib: defaultdict[str, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    ling_participantes: set[str] = field(default_factory=set)

    # Sentimento (condicional a config.sentiment_enabled).
    sentiment_enabled: bool = False
    sent_tons: defaultdict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    sent_participantes: set[str] = field(default_factory=set)

    # A2 — Atividade noturna (00h–05h).
    noturna_por_autor: Counter[str] = field(default_factory=Counter)
    total_noturna: int = 0


class ChatStatistics:
    """Gera estatísticas detalhadas sobre conversas"""

    # Listas de detecção de idioma carregadas do recurso i18n (R36.2) em vez de
    # literais embutidos. O conteúdo é idêntico ao histórico, preservando a
    # detecção de idiomas para o idioma padrão.
    _LANG_KEYWORDS = get_lang_keywords()
    _LANG_CODE_MAP = get_lang_code_map()
    _LANG_MIN_CHARS = 20
    _LANG_MESSAGE_LIMIT = 300
    _LANG_CHUNK_TARGET = 1500
    _LANG_MAX_CHUNKS = 20

    def __init__(
        self,
        threads: list[Thread],
        owner_username: str = "",
        owner_id: str = "",
        base_dir: Path | None = None,
    ):
        self.threads = threads
        self.owner_username = owner_username
        self.owner_id = owner_id
        self.base_dir = base_dir

    def generate_all(self) -> dict[str, Any]:
        """Gera todas as estatísticas"""
        logger.info("Gerando estatísticas...")
        all_messages = []
        for t in self.threads:
            all_messages.extend(t.messages)

        # R25.1: percorre a coleção de mensagens uma ÚNICA vez, alimentando os
        # acumuladores compartilhados. As métricas derivadas de iteração por
        # mensagem consomem esses acumuladores em vez de reiterar a coleção,
        # preservando resultados idênticos à implementação multi-passagem
        # (R25.2). Métricas inerentemente estruturais (por_conversa, sessões,
        # streaks, tempo de resposta, reciprocidade, grafo, etc.) continuam
        # iterando por thread; e as que exigem varreduras especiais
        # (integridade de anexos em disco, comparação de períodos e detecção de
        # idioma) permanecem com sua própria passagem dedicada.
        acc = self._single_pass_accumulate(all_messages)

        stats = {
            "resumo": self._resumo_geral(acc),
            "por_participante": self._stats_por_participante(acc),
            "por_conversa": self._stats_por_conversa(),
            "temporal": self._stats_temporal(acc),
            "midias": self._stats_midias(acc),
            "chamadas": self._stats_chamadas(acc),
            "palavras": self._stats_palavras(acc),
            "horarios": self._stats_horarios(acc),
            "top_conversas": self._top_conversas(),
            "tempo_resposta": self._stats_tempo_resposta(),
            "heatmap": self._stats_heatmap(acc),
            "reacoes": self._stats_reacoes(acc),
            "emojis": self._stats_emojis(acc),
            "integridade_anexos": self._stats_integridade_anexos(all_messages),
            "gaps": self._stats_gaps(),
            "grafo": self._grafo_data(),
            "tamanho_msgs": self._stats_tamanho_mensagens(acc),
            "comparacao_periodos": self._stats_comparacao_periodos(all_messages),
            "idiomas": self._stats_idiomas(all_messages),
            "timeline": self._stats_timeline(),
            "editadas": self._stats_editadas(acc),
            "pagamentos": self._stats_pagamentos(acc),
            "eventos_grupo": self._stats_eventos_grupo(acc),
            "removidas_temporal": self._stats_removidas_temporal(acc),
            "temporarias_temporal": self._stats_temporarias_temporal(acc),
            "dominios": self._stats_dominios(acc),
            "iniciativa": self._stats_iniciativa(),
            "reciprocidade": self._stats_reciprocidade(),
            "sessoes": self._stats_sessoes(),
            "esfriamento": self._stats_esfriamento(),
            "streaks": self._stats_streaks(),
            "ngramas": self._stats_ngramas(acc),
            "linguistico": self._stats_linguistico(acc),
            "timeline_contatos": stats_timeline_contatos(self.threads, self.owner_username),
            "atividade_noturna": stats_atividade_noturna(
                acc.noturna_por_autor, acc.total_noturna
            ),
            "iniciadores": stats_iniciadores(self.threads),
            "taxa_resposta": stats_taxa_resposta(self.threads, self.owner_username),
            "velocidade_conversa": stats_velocidade_conversa(self.threads),
            "rajadas": stats_rajadas(self.threads),
            "removidas_por_autor": stats_removidas_por_autor(self.threads),
            "timeline_links": stats_timeline_links(self.threads),
            "dominancia_grupo": stats_dominancia_grupo(self.threads),
            "midia_por_contato": stats_midia_por_contato(acc.participant_stats),
        }
        # R18: análise de sentimento offline é opcional e condicional. A família
        # ``sentimento`` só é registrada quando habilitada na configuração
        # (``config.sentiment_enabled``); quando desabilitada, a chave é omitida
        # da saída (R18.3), e os exportadores simplesmente não a encontram.
        if config.sentiment_enabled:
            stats["sentimento"] = self._stats_sentimento(acc)
        # R22: o sumário de insights automáticos é derivado das demais métricas
        # já calculadas (não relê as mensagens cruas). Por isso é montado por
        # último, consumindo o dicionário ``stats`` parcialmente preenchido.
        stats["insights"] = self._stats_insights(stats)
        logger.info("Estatísticas geradas com sucesso!")
        return stats

    def _single_pass_accumulate(self, messages: list[Message]) -> _PassAccumulators:
        """Percorre as mensagens uma única vez alimentando os acumuladores (R25).

        Esta é a passagem única exigida por R25.1: um único laço sobre a coleção
        de mensagens preenche todos os acumuladores que antes eram reconstruídos
        por métodos ``_stats_*`` independentes (cada um com sua própria varredura
        completa). A ordem de iteração é exatamente a mesma de ``all_messages``
        (threads em ordem, mensagens em ordem), de modo que a ordem de inserção
        nos ``Counter``/``defaultdict`` — e portanto o desempate de
        ``most_common`` e das ordenações estáveis — coincide com a implementação
        multi-passagem, garantindo resultados idênticos (R25.2).

        As condições de filtragem por métrica são reproduzidas verbatim das
        implementações originais para preservar o contrato de saída.
        """
        acc = _PassAccumulators()
        acc.total_msgs = len(messages)

        # Carregado uma única vez (idêntico a _stats_palavras/_stats_ngramas).
        stop_words = get_stop_words()
        # Capturado uma vez para gatear a acumulação de sentimento (R18).
        sentiment_enabled = config.sentiment_enabled
        acc.sentiment_enabled = sentiment_enabled

        # Padrão de pontuação das bordas, idêntico aos métodos originais.
        pontuacao = ".,!?;:()[]{}\"'…-_"

        for msg in messages:
            sent = msg.sent
            author = msg.author
            body = msg.body
            attachments = msg.attachments
            # Mensagens com corpo aproveitável (mesma regra de _stats_palavras,
            # _stats_ngramas, _stats_emojis, _stats_linguistico, _stats_sentimento).
            corpo_util = bool(body) and not msg.is_call and not msg.removed_by_sender

            # --- Resumo geral -------------------------------------------------
            if sent:
                if acc.primeira_data is None or sent < acc.primeira_data:
                    acc.primeira_data = sent
                if acc.ultima_data is None or sent > acc.ultima_data:
                    acc.ultima_data = sent
            acc.total_attachments += len(attachments)
            if msg.is_call:
                acc.total_calls += 1
            if msg.disappearing:
                acc.total_disappearing += 1
            if msg.removed_by_sender:
                acc.total_removed += 1
            if msg.share_url:
                acc.total_shares += 1
            if msg.is_reaction:
                acc.total_reactions += 1
            if msg.has_payment:
                acc.total_payments += 1
            if msg.subscription_event:
                acc.total_subscriptions += 1

            # --- Por participante --------------------------------------------
            ps = acc.participant_stats[author]
            ps["mensagens"] += 1
            ps["caracteres"] += len(body or "")
            ps["anexos"] += len(attachments)
            if msg.is_call:
                ps["chamadas"] += 1
            if msg.share_url:
                ps["links"] += 1
            if msg.is_reaction:
                ps["reacoes"] += 1
            for att in attachments:
                if "audio" in att.file_type:
                    ps["audios"] += 1
                elif "image" in att.file_type:
                    ps["fotos"] += 1
                elif "video" in att.file_type:
                    ps["videos"] += 1

            # --- Temporal -----------------------------------------------------
            if sent:
                acc.temporal_por_mes[sent.strftime("%Y-%m")] += 1
                acc.temporal_por_dia_semana[sent.weekday()] += 1
                acc.temporal_por_ano[sent.year] += 1

            # --- Mídias (ordem image/video/audio, distinta de por_participante) -
            for att in attachments:
                if "image" in att.file_type:
                    acc.midias_fotos += 1
                elif "video" in att.file_type:
                    acc.midias_videos += 1
                elif "audio" in att.file_type:
                    acc.midias_audios += 1
                else:
                    acc.midias_outros += 1

            # --- Chamadas -----------------------------------------------------
            if msg.is_call:
                acc.chamadas_total += 1
                if msg.call_missed:
                    acc.chamadas_perdidas += 1
                acc.chamadas_duracao_total += msg.call_duration
                if msg.call_type:
                    acc.chamadas_tipos[msg.call_type] += 1

            # --- Palavras -----------------------------------------------------
            if corpo_util:
                for word in body.lower().split():
                    clean = word.strip(pontuacao)
                    if len(clean) >= 2 and clean not in stop_words:
                        acc.palavras_counter[clean] += 1
                    acc.palavras_total += 1

            # --- Horários e heatmap ------------------------------------------
            if sent:
                acc.horarios_por_hora[sent.hour] += 1
                acc.heatmap_matrix[sent.weekday()][sent.hour] += 1
                # A2 — Atividade noturna (00h–05h inclusive 0..5)
                if 0 <= sent.hour < 6:
                    acc.noturna_por_autor[author] += 1
                    acc.total_noturna += 1

            # --- Reações por autor -------------------------------------------
            if msg.is_reaction:
                acc.reacoes_por_autor[author] += 1

            # --- Emojis -------------------------------------------------------
            if corpo_util:
                emojis_found = self._extract_emoji_clusters(body)
                if emojis_found:
                    acc.emoji_msgs_com_emoji += 1
                    for emoji in emojis_found:
                        # Cada char individual do match (pode ter ZWJ sequences).
                        for ch in emoji:
                            if ch not in ("\ufe0f", "\u200d", "\ufe0e"):
                                acc.emoji_counter[ch] += 1
                                acc.emoji_by_author[author][ch] += 1

            # --- Editadas -----------------------------------------------------
            if msg.is_edited:
                acc.editadas_total += 1
                acc.editadas_por_autor[author] += 1

            # --- Agregações temporais por período mensal ---------------------
            if sent:
                periodo = sent.strftime("%Y-%m")
                if msg.has_payment:
                    acc.pagamentos_por_periodo[periodo] += 1
                if msg.subscription_event or msg.subscription_users:
                    acc.eventos_por_periodo[periodo] += 1
                if msg.removed_by_sender:
                    acc.removidas_por_periodo[periodo] += 1
                if msg.disappearing:
                    acc.temporarias_por_periodo[periodo] += 1

            # --- Domínios de links -------------------------------------------
            if msg.share_url:
                try:
                    host = urlparse(msg.share_url).hostname
                except ValueError:
                    host = None
                if host:
                    acc.dominios_por_dominio[host] += 1

            # --- Tamanho de mensagens ----------------------------------------
            if body:
                length = len(body)
                acc.tamanho_total_chars += length
                acc.tamanho_total_msgs_com_texto += 1
                for lo, hi, label in self._TAMANHO_FAIXAS:
                    if lo <= length <= hi:
                        acc.tamanho_dist_geral[label] += 1
                        acc.tamanho_dist_por_autor[author][label] += 1
                        break

            # --- N-gramas -----------------------------------------------------
            if corpo_util:
                tokens: list[str] = []
                for word in body.lower().split():
                    clean = word.strip(pontuacao)
                    if len(clean) >= 2 and clean not in stop_words:
                        tokens.append(clean)
                for i in range(len(tokens) - 1):
                    acc.ngramas_bigramas[f"{tokens[i]} {tokens[i + 1]}"] += 1
                for i in range(len(tokens) - 2):
                    acc.ngramas_trigramas[f"{tokens[i]} {tokens[i + 1]} {tokens[i + 2]}"] += 1

            # --- Métricas linguísticas ---------------------------------------
            acc.ling_participantes.add(author)
            if sent:
                for faixa, horas, _ in self._FAIXAS_HORARIAS:
                    if sent.hour in horas:
                        acc.ling_distrib[author][faixa] += 1
                        break
            if corpo_util:
                if "?" in body:
                    acc.ling_perguntas[author] += 1
                else:
                    acc.ling_afirmacoes[author] += 1
                for word in body.lower().split():
                    clean = word.strip(pontuacao)
                    if clean:
                        acc.ling_tokens_total[author] += 1
                        acc.ling_tokens_unicos[author].add(clean)

            # --- Sentimento (condicional) ------------------------------------
            if sentiment_enabled:
                acc.sent_participantes.add(author)
                if corpo_util:
                    positivos = 0
                    negativos = 0
                    for word in body.split():
                        token = self._normalizar_token(word)
                        if not token:
                            continue
                        if token in self._LEXICO_POSITIVO:
                            positivos += 1
                        elif token in self._LEXICO_NEGATIVO:
                            negativos += 1
                    if positivos > negativos:
                        tom = "positivo"
                    elif negativos > positivos:
                        tom = "negativo"
                    else:
                        tom = "neutro"
                    acc.sent_tons[author][tom] += 1

        return acc

    def filtrar(self, filtro: "StatsFilter | dict[str, Any] | None") -> "ChatStatistics":
        """Recalcula sobre um subconjunto, retornando nova ``ChatStatistics`` (R19).

        Aplica o ``filtro`` (por conversa e/ou intervalo de datas) às conversas
        atuais e devolve uma nova instância contendo apenas as mensagens que o
        satisfazem. As conversas são copiadas (``dataclasses.replace``) com a
        lista de mensagens filtrada, preservando participantes e metadados; as
        conversas que ficam sem mensagens são descartadas. Como a nova instância
        é uma ``ChatStatistics`` comum, ``generate_all()`` produz exatamente as
        métricas do subconjunto — equivalentes às que seriam calculadas
        diretamente sobre aquele subconjunto (R19.1, R19.2). Sem filtro, devolve
        o conjunto global (R19.3). Um filtro que não retorna mensagens produz uma
        instância sem conversas, cujo ``generate_all()`` reporta zeros sem erro
        (R19.4).
        """
        filtro = StatsFilter.coerce(filtro)

        if filtro.is_empty():
            return self

        novas_threads: list[Thread] = []
        for thread in self.threads:
            if not filtro.match_thread(thread):
                continue
            msgs = [m for m in thread.messages if filtro.match_message(m)]
            if not msgs:
                continue
            novas_threads.append(replace(thread, messages=msgs))

        return ChatStatistics(
            novas_threads,
            owner_username=self.owner_username,
            owner_id=self.owner_id,
            base_dir=self.base_dir,
        )

    def _stats_insights(self, stats: dict[str, Any]) -> dict[str, Any]:
        """Sumário de insights automáticos derivado das demais métricas (R22).

        Calcula os destaques exibidos no topo do relatório a partir do conjunto
        analisado (R22.2), reutilizando estruturas já computadas em
        ``generate_all`` em vez de reler as mensagens cruas:

        - ``picos_atividade``: hora mais ativa (de ``horarios``), dia da semana
          mais ativo e mês de maior volume (de ``temporal``).
        - ``contato_mais_ativo``: participante com mais mensagens (de
          ``por_participante``, já ordenado em ordem decrescente).
        - ``resposta_mais_rapida``: participante com a menor mediana de tempo de
          resposta em DMs (de ``tempo_resposta``).

        Cada item só é incluído quando há dados suficientes para calculá-lo;
        itens sem dados são omitidos sem erro (R22.3). Um conjunto sem mensagens
        produz um dicionário de insights vazio.
        """
        insights: dict[str, Any] = {}

        # --- Picos de atividade -------------------------------------------
        horarios = stats.get("horarios") or {}
        temporal = stats.get("temporal") or {}
        picos: dict[str, Any] = {}

        por_hora = horarios.get("por_hora") or []
        if any((h.get("total") or 0) > 0 for h in por_hora):
            picos["hora"] = horarios.get("hora_mais_ativa")

        por_dia_semana = temporal.get("por_dia_semana") or []
        if any((d.get("total") or 0) > 0 for d in por_dia_semana):
            picos["dia_semana"] = temporal.get("dia_mais_ativo")

        por_mes = temporal.get("por_mes") or []
        if por_mes:
            mes_pico = max(por_mes, key=lambda m: m.get("total") or 0)
            picos["mes"] = {"mes": mes_pico["mes"], "total": mes_pico["total"]}

        if picos:
            insights["picos_atividade"] = picos

        # --- Contato mais ativo -------------------------------------------
        participantes = stats.get("por_participante") or []
        if participantes:
            # A lista já vem ordenada por nº de mensagens (desc); o topo é o
            # contato mais ativo. Ignora entradas sem mensagens.
            topo = participantes[0]
            if (topo.get("mensagens") or 0) > 0:
                insights["contato_mais_ativo"] = {
                    "nome": topo.get("nome", ""),
                    "mensagens": topo.get("mensagens", 0),
                }

        # --- Resposta mais rápida -----------------------------------------
        tempo_resposta = stats.get("tempo_resposta") or []
        if tempo_resposta:
            mais_rapida = min(tempo_resposta, key=lambda r: r.get("mediana_segundos", float("inf")))
            insights["resposta_mais_rapida"] = {
                "nome": mais_rapida.get("nome", ""),
                "mediana_segundos": mais_rapida.get("mediana_segundos", 0),
                "mediana_formatada": mais_rapida.get("mediana_formatada", ""),
            }

        return insights

    def _resumo_geral(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Resumo geral de todas as conversas"""
        total_msgs = acc.total_msgs
        total_threads = len(self.threads)

        first_date = acc.primeira_data
        last_date = acc.ultima_data

        total_attachments = acc.total_attachments
        total_calls = acc.total_calls
        total_disappearing = acc.total_disappearing
        total_removed = acc.total_removed
        total_shares = acc.total_shares
        total_reactions = acc.total_reactions
        total_payments = acc.total_payments
        total_subscriptions = acc.total_subscriptions

        # Participantes únicos
        participants = set()
        for t in self.threads:
            for p in t.participants:
                participants.add(p[0])

        # Classificação DM vs Grupo
        total_dms = sum(1 for t in self.threads if len(t.participants) <= 2)
        total_grupos = sum(1 for t in self.threads if len(t.participants) > 2)
        msgs_dms = sum(len(t.messages) for t in self.threads if len(t.participants) <= 2)
        msgs_grupos = sum(len(t.messages) for t in self.threads if len(t.participants) > 2)

        # Média de mensagens por dia
        if first_date and last_date:
            days = max((last_date - first_date).days, 1)
            msgs_per_day = total_msgs / days
        else:
            days = 0
            msgs_per_day = 0

        return {
            "total_mensagens": total_msgs,
            "total_conversas": total_threads,
            "total_participantes": len(participants),
            "total_anexos": total_attachments,
            "total_chamadas": total_calls,
            "total_temporarias": total_disappearing,
            "total_removidas": total_removed,
            "total_compartilhamentos": total_shares,
            "primeira_mensagem": first_date.strftime("%d/%m/%Y %H:%M") if first_date else "N/A",
            "ultima_mensagem": last_date.strftime("%d/%m/%Y %H:%M") if last_date else "N/A",
            "periodo_dias": days,
            "media_mensagens_dia": round(msgs_per_day, 1),
            "total_reacoes": total_reactions,
            "total_pagamentos": total_payments,
            "total_eventos_grupo": total_subscriptions,
            "total_dms": total_dms,
            "total_grupos": total_grupos,
            "msgs_dms": msgs_dms,
            "msgs_grupos": msgs_grupos,
        }

    def _stats_por_participante(self, acc: _PassAccumulators) -> list[dict[str, Any]]:
        """Estatísticas por participante"""
        participant_stats = acc.participant_stats

        result: list[dict[str, Any]] = []
        for name, data in participant_stats.items():
            avg_chars = data["caracteres"] / max(data["mensagens"], 1)
            result.append(
                {
                    "nome": name,
                    "mensagens": data["mensagens"],
                    "caracteres_total": data["caracteres"],
                    "media_caracteres": round(avg_chars, 1),
                    "anexos": data["anexos"],
                    "chamadas": data["chamadas"],
                    "audios": data["audios"],
                    "fotos": data["fotos"],
                    "videos": data["videos"],
                    "links": data["links"],
                    "reacoes": data["reacoes"],
                }
            )

        result.sort(key=lambda x: x["mensagens"], reverse=True)
        return result

    def _stats_por_conversa(self) -> list[dict[str, Any]]:
        """Estatísticas por conversa"""
        result = []
        for t in self.threads:
            participants = [p[0] for p in t.participants]
            dates = [m.sent for m in t.messages if m.sent]
            first = min(dates) if dates else None
            last = max(dates) if dates else None

            attachments = sum(len(m.attachments) for m in t.messages)
            calls = sum(1 for m in t.messages if m.is_call)

            name = t.thread_name or ", ".join(participants[:3])
            tipo = "Grupo" if len(t.participants) > 2 else "DM"

            result.append(
                {
                    "nome": name,
                    "thread_id": t.thread_id,
                    "tipo": tipo,
                    "participantes": len(t.participants),
                    "mensagens": len(t.messages),
                    "anexos": attachments,
                    "chamadas": calls,
                    "primeira_msg": first.strftime("%d/%m/%Y") if first else "N/A",
                    "ultima_msg": last.strftime("%d/%m/%Y") if last else "N/A",
                }
            )

        result.sort(key=lambda x: x["mensagens"], reverse=True)
        return result

    def _stats_temporal(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas temporais - mensagens por mês, semana, dia da semana"""
        por_mes = acc.temporal_por_mes
        por_dia_semana = acc.temporal_por_dia_semana
        por_ano = acc.temporal_por_ano

        dias_semana_nomes = get_weekday_names()

        # Ordenar meses cronologicamente
        meses_ordenados = sorted(por_mes.items())

        # Dia da semana mais ativo
        dia_mais_ativo = (
            max(por_dia_semana, key=lambda d: por_dia_semana[d]) if por_dia_semana else 0
        )

        return {
            "por_mes": [{"mes": k, "total": v} for k, v in meses_ordenados],
            "por_dia_semana": [
                {"dia": dias_semana_nomes[i], "total": por_dia_semana.get(i, 0)} for i in range(7)
            ],
            "por_ano": [{"ano": k, "total": v} for k, v in sorted(por_ano.items())],
            "dia_mais_ativo": dias_semana_nomes[dia_mais_ativo],
        }

    def _stats_midias(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de mídias"""
        fotos = acc.midias_fotos
        videos = acc.midias_videos
        audios = acc.midias_audios
        outros = acc.midias_outros

        return {
            "fotos": fotos,
            "videos": videos,
            "audios": audios,
            "outros": outros,
            "total": fotos + videos + audios + outros,
        }

    def _stats_chamadas(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de chamadas"""
        total = acc.chamadas_total
        perdidas = acc.chamadas_perdidas
        duracao_total = acc.chamadas_duracao_total
        tipos = acc.chamadas_tipos

        return {
            "total": total,
            "perdidas": perdidas,
            "atendidas": total - perdidas,
            "duracao_total_segundos": duracao_total,
            "duracao_total_formatada": f"{duracao_total // 3600}h {(duracao_total % 3600) // 60}m",
            "duracao_media_segundos": round(duracao_total / max(total - perdidas, 1)),
            "por_tipo": dict(tipos),
        }

    def _stats_palavras(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de palavras mais usadas"""
        word_counter = acc.palavras_counter
        total_words = acc.palavras_total

        top_50 = word_counter.most_common(50)

        return {
            "total_palavras": total_words,
            "palavras_unicas": len(word_counter),
            "top_50": [{"palavra": w, "contagem": c} for w, c in top_50],
        }

    def _stats_horarios(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas por horário do dia"""
        por_hora = acc.horarios_por_hora

        hora_mais_ativa = max(por_hora, key=lambda h: por_hora[h]) if por_hora else 0

        # Classificação por período
        madrugada = sum(por_hora.get(h, 0) for h in range(0, 6))
        manha = sum(por_hora.get(h, 0) for h in range(6, 12))
        tarde = sum(por_hora.get(h, 0) for h in range(12, 18))
        noite = sum(por_hora.get(h, 0) for h in range(18, 24))

        return {
            "por_hora": [{"hora": f"{h:02d}:00", "total": por_hora.get(h, 0)} for h in range(24)],
            "hora_mais_ativa": f"{hora_mais_ativa:02d}:00",
            "periodos": {
                "madrugada": madrugada,
                "manha": manha,
                "tarde": tarde,
                "noite": noite,
            },
        }

    def _top_conversas(self, limit: int = 10) -> list[dict[str, Any]]:
        """Top conversas por número de mensagens"""
        convs = []
        for t in self.threads:
            participants = [p[0] for p in t.participants]
            name = t.thread_name or ", ".join(participants[:3])
            convs.append(
                {
                    "nome": name,
                    "mensagens": len(t.messages),
                    "participantes": len(t.participants),
                }
            )

        convs.sort(key=lambda x: x["mensagens"], reverse=True)
        return convs[:limit]

    def _stats_tempo_resposta(self) -> list[dict[str, Any]]:
        """Análise de tempo de resposta em conversas diretas (DMs)"""
        response_times = defaultdict(list)

        for thread in self.threads:
            if len(thread.participants) != 2:
                continue

            msgs = [m for m in thread.messages if m.sent and not m.is_call and not m.is_reaction]
            if len(msgs) < 2:
                continue

            msgs.sort(key=lambda m: m.sent)

            for i in range(1, len(msgs)):
                prev = msgs[i - 1]
                curr = msgs[i]

                if prev.author != curr.author:
                    delta = (curr.sent - prev.sent).total_seconds()
                    if 0 < delta <= 86400:  # Max 24h
                        response_times[curr.author].append(delta)

        result = []
        for author, times in response_times.items():
            if len(times) >= 3:
                avg = sum(times) / len(times)
                # statistics.median trata corretamente o caso par (média dos dois
                # centrais) e ímpar (elemento central), ao contrário da indexação manual.
                median = statistics.median(times)
                result.append(
                    {
                        "nome": author,
                        "media_segundos": round(avg),
                        "mediana_segundos": round(median),
                        "media_formatada": self._format_duration(avg),
                        "mediana_formatada": self._format_duration(median),
                        "total_respostas": len(times),
                        "mais_rapida": self._format_duration(min(times)),
                        "mais_lenta": self._format_duration(max(times)),
                    }
                )

        result.sort(key=lambda x: x["media_segundos"])
        return result

    def _format_duration(self, seconds: float) -> str:
        """Formata duração em formato legível"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}min{s:02d}s"
        else:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            return f"{h}h{m:02d}min"

    def _stats_heatmap(self, acc: _PassAccumulators) -> list[list[int]]:
        """Gera matriz dia×hora para heatmap de atividade"""
        return acc.heatmap_matrix

    def _stats_reacoes(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de reações (curtidas e reações a mensagens)"""
        total = acc.total_reactions
        by_author = acc.reacoes_por_autor

        return {
            "total": total,
            "por_autor": [{"nome": n, "total": c} for n, c in by_author.most_common(10)],
        }

    def _stats_editadas(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de mensagens editadas (R7).

        Calcula o total de mensagens com ``is_edited`` verdadeiro e a contagem
        por autor, ordenada em ordem decrescente. Um conjunto sem mensagens
        editadas reporta total zero sem erro. A soma das contagens por autor
        sempre iguala o total reportado (todos os autores com edições são
        incluídos, sem truncamento).
        """
        total = acc.editadas_total
        by_author = acc.editadas_por_autor

        return {
            "total": total,
            "por_autor": [{"nome": n, "total": c} for n, c in by_author.most_common()],
        }

    def _stats_pagamentos(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de pagamentos ao longo do tempo (R8.1, R8.2, R8.5).

        Conta as mensagens com ``has_payment`` verdadeiro e as agrega por
        período mensal (``%Y-%m``). A lista ``por_periodo`` é ordenada
        cronologicamente e o ``total`` sempre iguala a soma das contagens por
        período (apenas mensagens datadas entram na agregação, de modo que a
        propriedade de conservação se mantém). Um conjunto sem pagamentos
        reporta ``total`` zero e lista vazia, sem erro.
        """
        por_periodo = acc.pagamentos_por_periodo

        total = sum(por_periodo.values())

        return {
            "total": total,
            "por_periodo": [
                {"periodo": periodo, "contagem": contagem}
                for periodo, contagem in sorted(por_periodo.items())
            ],
        }

    def _stats_eventos_grupo(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de eventos de grupo ao longo do tempo (R8.3, R8.4, R8.5).

        Conta os eventos de grupo derivados de ``subscription_event`` (entrada/
        saída) ou ``subscription_users`` (lista de usuários afetados) e os agrega
        por período mensal (``%Y-%m``). Uma mensagem é considerada evento de
        grupo quando possui ``subscription_event`` não vazio ou
        ``subscription_users`` não vazio. A lista ``por_periodo`` é ordenada
        cronologicamente e o ``total`` sempre iguala a soma das contagens por
        período (apenas eventos datados entram na agregação). Um conjunto sem
        eventos de grupo reporta ``total`` zero e lista vazia, sem erro.
        """
        por_periodo = acc.eventos_por_periodo

        total = sum(por_periodo.values())

        return {
            "total": total,
            "por_periodo": [
                {"periodo": periodo, "contagem": contagem}
                for periodo, contagem in sorted(por_periodo.items())
            ],
        }

    def _stats_removidas_temporal(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de mensagens removidas ao longo do tempo (R9.1, R9.3, R9.4).

        Conta as mensagens com ``removed_by_sender`` verdadeiro e as agrega por
        período mensal (``%Y-%m``). A lista ``por_periodo`` é ordenada
        cronologicamente e o ``total`` sempre iguala a soma das contagens por
        período (apenas mensagens datadas entram na agregação, de modo que a
        propriedade de conservação se mantém). Um conjunto sem mensagens
        removidas reporta ``total`` zero e lista vazia, sem erro.
        """
        por_periodo = acc.removidas_por_periodo

        total = sum(por_periodo.values())

        return {
            "total": total,
            "por_periodo": [
                {"periodo": periodo, "contagem": contagem}
                for periodo, contagem in sorted(por_periodo.items())
            ],
        }

    def _stats_temporarias_temporal(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de mensagens temporárias ao longo do tempo (R9.2, R9.3, R9.4).

        Conta as mensagens com ``disappearing`` verdadeiro (mensagens efêmeras)
        e as agrega por período mensal (``%Y-%m``). A lista ``por_periodo`` é
        ordenada cronologicamente e o ``total`` sempre iguala a soma das
        contagens por período (apenas mensagens datadas entram na agregação).
        Um conjunto sem mensagens temporárias reporta ``total`` zero e lista
        vazia, sem erro.
        """
        por_periodo = acc.temporarias_por_periodo

        total = sum(por_periodo.values())

        return {
            "total": total,
            "por_periodo": [
                {"periodo": periodo, "contagem": contagem}
                for periodo, contagem in sorted(por_periodo.items())
            ],
        }

    def _stats_dominios(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de domínios de links compartilhados (R10.1, R10.2, R10.3, R10.4).

        Para cada mensagem com ``share_url`` não vazio, extrai o host (domínio)
        usando ``urllib.parse.urlparse`` e agrega a contagem por domínio. Os
        domínios são expostos ordenados por contagem em ordem decrescente
        (desempate alfabético para estabilidade). URLs sem host válido (por
        exemplo, sem esquema ou malformadas) são excluídas da agregação sem
        interromper o cálculo. O ``total`` sempre iguala o número de mensagens
        cujo ``share_url`` produz um host válido — ou seja, a soma das contagens
        por domínio. Um conjunto sem links válidos reporta ``total`` zero e
        lista vazia, sem erro.
        """
        por_dominio = acc.dominios_por_dominio

        total = sum(por_dominio.values())

        return {
            "total": total,
            "por_dominio": [
                {"dominio": dominio, "contagem": contagem}
                # Ordena por contagem decrescente; desempata pelo nome do
                # domínio para uma ordenação determinística.
                for dominio, contagem in sorted(
                    por_dominio.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        }

    def _stats_iniciativa(self) -> dict[str, Any]:
        """Indicador de iniciativa: quem inicia e encerra conversas (R11).

        Para cada conversa, percorre as mensagens datadas em ordem cronológica
        e usa o limiar de gap configurável (``config.session_gap_minutes``) para
        delimitar sessões. A primeira mensagem da conversa é sempre um início e
        a última é sempre um encerramento. Quando o intervalo entre duas
        mensagens consecutivas excede o limiar (R11.1), a mensagem posterior é
        marcada como início de conversa e a mensagem anterior como encerramento
        da conversa precedente. Cada início é atribuído ao autor da mensagem que
        o iniciou (R11.2) e cada encerramento ao autor da última mensagem antes
        do gap (R11.3). As contagens são reportadas por autor (R11.4).

        Por construção, o total de inícios iguala o número de sessões e o total
        de encerramentos iguala o total de inícios, pois cada sessão tem
        exatamente um início e um encerramento. Conversas sem mensagens datadas
        não contribuem e um conjunto vazio reporta listas e totais zerados sem
        erro.
        """
        # Limiar de gap como timedelta a partir da configuração (R11.1).
        gap_threshold = timedelta(minutes=config.session_gap_minutes)

        inicios_por_autor: Counter[str] = Counter()
        encerramentos_por_autor: Counter[str] = Counter()

        for thread in self.threads:
            # Apenas mensagens datadas participam; ordenadas cronologicamente.
            dated = sorted((m for m in thread.messages if m.sent), key=lambda m: m.sent)
            if not dated:
                continue

            # A primeira mensagem inicia a primeira sessão.
            inicios_por_autor[dated[0].author] += 1

            for i in range(1, len(dated)):
                gap = dated[i].sent - dated[i - 1].sent
                if gap > gap_threshold:
                    # A mensagem anterior encerra a sessão precedente (R11.3) e
                    # a posterior inicia uma nova sessão (R11.1, R11.2).
                    encerramentos_por_autor[dated[i - 1].author] += 1
                    inicios_por_autor[dated[i].author] += 1

            # A última mensagem encerra a sessão final (R11.3).
            encerramentos_por_autor[dated[-1].author] += 1

        # Reúne todos os autores com inícios ou encerramentos (R11.4).
        autores = set(inicios_por_autor) | set(encerramentos_por_autor)
        por_autor: list[dict[str, Any]] = [
            {
                "nome": autor,
                "inicios": inicios_por_autor.get(autor, 0),
                "encerramentos": encerramentos_por_autor.get(autor, 0),
            }
            for autor in autores
        ]
        # Ordena por inícios (desc) e desempata pelo nome para determinismo.
        por_autor.sort(key=lambda item: (-item["inicios"], item["nome"]))

        return {
            "total_inicios": sum(inicios_por_autor.values()),
            "total_encerramentos": sum(encerramentos_por_autor.values()),
            "por_autor": por_autor,
        }

    def _stats_reciprocidade(self) -> list[dict[str, Any]]:
        """Índice de reciprocidade por DM (R12).

        Uma DM é uma conversa com exatamente dois participantes (R12.4); demais
        conversas (grupos ou conversas com menos de dois participantes) são
        excluídas do cálculo. Para cada DM, calcula a proporção de mensagens
        (R12.1) e de caracteres (R12.2) enviados por cada um dos dois lados e
        expõe um índice de reciprocidade em [0, 1] (R12.3), definido como a
        razão ``min / max`` entre os dois lados:

        - ``1.0`` representa equilíbrio perfeito (ambos enviam a mesma
          quantidade);
        - valores próximos de ``0`` indicam conversa fortemente unilateral.

        Os autores considerados são os dois participantes da DM. Mensagens de
        autores fora dos participantes registrados (caso raro) são ignoradas no
        cálculo, mantendo o índice restrito aos dois lados da DM.

        Tratamento de divisão por zero: quando ambos os lados têm contagem zero
        (ex.: DM sem mensagens, ou sem caracteres), o índice é ``1.0`` (vacuamente
        equilibrado); quando apenas um lado é zero e o outro é positivo, o índice
        é ``0.0`` (totalmente unilateral). Esses casos derivam naturalmente da
        razão ``min / max`` quando o denominador é positivo, e do ramo explícito
        quando ``max`` é zero.
        """

        def _indice(a: int, b: int) -> float:
            maior = max(a, b)
            if maior == 0:
                # Ambos zero: vacuamente equilibrado.
                return 1.0
            return min(a, b) / maior

        resultado: list[dict[str, Any]] = []

        for thread in self.threads:
            # Apenas DMs (exatamente dois participantes) entram no cálculo (R12.4).
            if len(thread.participants) != 2:
                continue

            nome_a = thread.participants[0][0]
            nome_b = thread.participants[1][0]

            msgs_por_autor: Counter[str] = Counter()
            chars_por_autor: Counter[str] = Counter()

            for msg in thread.messages:
                if msg.author not in (nome_a, nome_b):
                    continue
                msgs_por_autor[msg.author] += 1
                chars_por_autor[msg.author] += len(msg.body or "")

            indice_msgs = _indice(msgs_por_autor[nome_a], msgs_por_autor[nome_b])
            indice_chars = _indice(chars_por_autor[nome_a], chars_por_autor[nome_b])

            resultado.append(
                {
                    "thread_id": thread.thread_id,
                    "indice_msgs": round(indice_msgs, 4),
                    "indice_chars": round(indice_chars, 4),
                }
            )

        return resultado

    def _stats_sessoes(self) -> list[dict[str, Any]]:
        """Sessões de conversa por conversa (R13).

        Para cada conversa, percorre as mensagens datadas em ordem cronológica
        e usa o limiar de gap configurável (``config.session_gap_minutes``,
        padrão 30 min) para delimitar sessões (R13.1). Uma nova sessão começa
        sempre que o intervalo entre duas mensagens consecutivas excede o
        limiar; caso contrário, a mensagem pertence à sessão corrente.

        Para cada conversa reporta o número de sessões (``num_sessoes``) e a
        duração média das sessões em segundos (``duracao_media_segundos``)
        (R13.2). A duração de uma sessão é ``última - primeira`` mensagem dessa
        sessão; portanto uma sessão com uma única mensagem tem duração zero, e
        uma conversa com uma única mensagem reporta uma sessão com duração média
        zero (R13.3, R13.4).

        Por construção, a soma das mensagens entre as sessões de uma conversa
        sempre iguala o total de mensagens datadas dessa conversa (Propriedade
        12). Conversas sem mensagens datadas não contribuem; um conjunto vazio
        reporta lista vazia sem erro.
        """
        # Limiar de gap como timedelta a partir da configuração (R13.1).
        gap_threshold = timedelta(minutes=config.session_gap_minutes)

        resultado: list[dict[str, Any]] = []

        for thread in self.threads:
            # Apenas mensagens datadas participam; ordenadas cronologicamente.
            dated = sorted((m for m in thread.messages if m.sent), key=lambda m: m.sent)
            if not dated:
                continue

            # Acumula as durações de cada sessão (em segundos). A sessão começa
            # na primeira mensagem; sempre que o gap excede o limiar, fecha-se a
            # sessão corrente e inicia-se uma nova.
            duracoes: list[float] = []
            inicio_sessao = dated[0].sent
            fim_sessao = dated[0].sent

            for i in range(1, len(dated)):
                gap = dated[i].sent - dated[i - 1].sent
                if gap > gap_threshold:
                    # Fecha a sessão corrente e registra sua duração.
                    duracoes.append((fim_sessao - inicio_sessao).total_seconds())
                    # Inicia uma nova sessão na mensagem posterior ao gap.
                    inicio_sessao = dated[i].sent
                fim_sessao = dated[i].sent

            # Fecha a última sessão em aberto.
            duracoes.append((fim_sessao - inicio_sessao).total_seconds())

            num_sessoes = len(duracoes)
            # Média das durações; com uma única mensagem (sessão de duração
            # zero) a média é zero (R13.4).
            duracao_media = sum(duracoes) / num_sessoes

            resultado.append(
                {
                    "thread_id": thread.thread_id,
                    "num_sessoes": num_sessoes,
                    "duracao_media_segundos": round(duracao_media, 1),
                }
            )

        return resultado

    def _stats_esfriamento(self) -> list[dict[str, Any]]:
        """Evolução do contato e detecção de esfriamento por conversa (R14).

        Para cada conversa, calcula o volume de mensagens por período mensal
        (``%Y-%m``) usando apenas mensagens datadas, e expõe essa série temporal
        em ordem cronológica (R14.1, R14.3). A série é a lista
        ``serie_temporal`` de ``{"periodo": "%Y-%m", "total": int}``.

        Regra de esfriamento (R14.2, R14.4) — uma conversa é sinalizada como em
        esfriamento (``em_esfriamento = True``) quando TODAS as condições abaixo
        se verificam sobre a série temporal de volume ``v[0], v[1], ..., v[n-1]``
        (em ordem cronológica):

        1. A série tem pelo menos 2 períodos (``n >= 2``); com um único período
           não há tendência a avaliar.
        2. O volume é monotonicamente não-crescente ao longo de períodos
           consecutivos, isto é, ``v[i] <= v[i-1]`` para todo ``i`` (queda
           sustentada, sem repiques de volume).
        3. A queda relativa total do primeiro ao último período excede o limiar
           configurável ``config.cooling_threshold`` (padrão 0.5), ou seja,
           ``(v[0] - v[-1]) / v[0] > config.cooling_threshold`` (exige
           ``v[0] > 0``).

        Esta regra distingue corretamente os três casos da Propriedade 13:

        - **Decrescente sustentada além do limiar** → sinalizada (condições 2 e
          3 satisfeitas).
        - **Estável** (todos os períodos iguais) → não sinalizada, pois a queda
          relativa é ``0`` e não excede o limiar (condição 3 falha).
        - **Crescente** → não sinalizada, pois viola a monotonicidade
          não-crescente (condição 2 falha) e a queda seria negativa.

        Conversas sem mensagens datadas reportam série vazia e
        ``em_esfriamento = False`` (não há tendência); um conjunto vazio reporta
        lista vazia sem erro.
        """
        # Limiar de esfriamento configurável (R14.4): fração mínima de queda
        # relativa total para considerar a conversa em esfriamento.
        limiar = config.cooling_threshold

        resultado: list[dict[str, Any]] = []

        for thread in self.threads:
            # Volume de mensagens por período mensal, apenas mensagens datadas (R14.1).
            por_periodo: Counter[str] = Counter()
            for msg in thread.messages:
                if msg.sent:
                    por_periodo[msg.sent.strftime("%Y-%m")] += 1

            # Série temporal em ordem cronológica, exposta para a detecção (R14.3).
            serie_ordenada = sorted(por_periodo.items())
            serie_temporal = [
                {"periodo": periodo, "total": total} for periodo, total in serie_ordenada
            ]

            volumes = [total for _, total in serie_ordenada]
            em_esfriamento = self._detectar_esfriamento(volumes, limiar)

            resultado.append(
                {
                    "thread_id": thread.thread_id,
                    "serie_temporal": serie_temporal,
                    "em_esfriamento": em_esfriamento,
                }
            )

        return resultado

    @staticmethod
    def _detectar_esfriamento(volumes: list[int], limiar: float) -> bool:
        """Aplica a regra de esfriamento (R14.2) sobre a série de volumes.

        Ver a documentação de :meth:`_stats_esfriamento` para a definição
        completa da regra. Retorna ``True`` somente quando a série tem ao menos
        dois períodos, é monotonicamente não-crescente e a queda relativa total
        excede ``limiar``.
        """
        # Condição 1: precisa de pelo menos dois períodos para haver tendência.
        if len(volumes) < 2:
            return False

        primeiro = volumes[0]
        # A queda relativa exige um ponto de partida positivo.
        if primeiro <= 0:
            return False

        # Condição 2: monotonicamente não-crescente (queda sustentada).
        for i in range(1, len(volumes)):
            if volumes[i] > volumes[i - 1]:
                return False

        # Condição 3: queda relativa total acima do limiar configurável.
        queda_relativa = (primeiro - volumes[-1]) / primeiro
        return queda_relativa > limiar

    def _stats_streaks(self) -> list[dict[str, Any]]:
        """Streaks de dias consecutivos com mensagem por conversa (R15).

        Para cada conversa, reúne o conjunto de datas distintas (``date()`` de
        cada mensagem datada) e calcula a maior sequência de dias de calendário
        consecutivos com pelo menos uma mensagem (R15.1). Reporta o comprimento
        dessa sequência (``maior_streak_dias``) e as datas de início e fim do
        intervalo (``inicio``/``fim``, formato ``%Y-%m-%d``) (R15.2).

        Por construção, o comprimento da maior sequência sempre iguala
        ``(fim - inicio) em dias + 1`` do intervalo reportado (Propriedade 14),
        pois o intervalo é composto por dias estritamente consecutivos.

        Uma conversa sem mensagens datadas reporta ``maior_streak_dias = 0`` e
        ``inicio``/``fim`` vazios (R15.3); um conjunto vazio reporta lista vazia
        sem erro.
        """
        resultado: list[dict[str, Any]] = []

        for thread in self.threads:
            # Conjunto de datas distintas (apenas mensagens datadas); ordenadas
            # cronologicamente para varrer sequências consecutivas.
            datas = sorted({m.sent.date() for m in thread.messages if m.sent})

            if not datas:
                # Sem datas: streak de comprimento zero e intervalo vazio (R15.3).
                resultado.append(
                    {
                        "thread_id": thread.thread_id,
                        "maior_streak_dias": 0,
                        "inicio": "",
                        "fim": "",
                    }
                )
                continue

            # Varredura: rastreia a sequência corrente e a melhor já vista. Uma
            # nova sequência começa sempre que o dia atual não é exatamente o dia
            # seguinte ao anterior.
            melhor_inicio = inicio_corrente = datas[0]
            melhor_fim = datas[0]

            for i in range(1, len(datas)):
                if datas[i] - datas[i - 1] == timedelta(days=1):
                    # Dia consecutivo: estende a sequência corrente.
                    fim_corrente = datas[i]
                else:
                    # Quebra de sequência: reinicia a partir do dia atual.
                    inicio_corrente = datas[i]
                    fim_corrente = datas[i]

                # Atualiza a melhor sequência quando a corrente a supera.
                if (fim_corrente - inicio_corrente) > (melhor_fim - melhor_inicio):
                    melhor_inicio = inicio_corrente
                    melhor_fim = fim_corrente

            maior_streak = (melhor_fim - melhor_inicio).days + 1

            resultado.append(
                {
                    "thread_id": thread.thread_id,
                    "maior_streak_dias": maior_streak,
                    "inicio": melhor_inicio.strftime("%Y-%m-%d"),
                    "fim": melhor_fim.strftime("%Y-%m-%d"),
                }
            )

        return resultado

    def _stats_ngramas(self, acc: _PassAccumulators, limite: int = 30) -> dict[str, Any]:
        """Bigramas e trigramas mais frequentes do conjunto de mensagens (R16).

        A tokenização espelha ``_stats_palavras``: o corpo de cada mensagem é
        convertido para minúsculas, dividido por espaços e cada token tem a
        pontuação das bordas removida. Tokens com menos de dois caracteres ou
        que sejam stop words (recurso i18n, R36.2) são descartados (R16.3),
        de modo que nenhum bigrama ou trigrama contém stop words.

        Os n-gramas são formados a partir de tokens *adjacentes que sobraram*
        dentro de cada mensagem (não atravessam a fronteira entre mensagens),
        contados e expostos ordenados por frequência em ordem decrescente
        (R16.1, R16.2, R16.4); o desempate é alfabético para uma ordenação
        determinística. Cada n-grama é a junção dos tokens separados por espaço.
        A saída é limitada aos ``limite`` n-gramas mais frequentes de cada tipo.

        Um conjunto sem tokens suficientes reporta listas vazias sem erro.
        """
        bigramas = acc.ngramas_bigramas
        trigramas = acc.ngramas_trigramas

        def _ordenar(contador: Counter[str]) -> list[dict[str, Any]]:
            # Ordena por contagem decrescente; desempata pelo n-grama para uma
            # ordenação determinística. Limita aos mais frequentes.
            return [
                {"ngrama": ngrama, "contagem": contagem}
                for ngrama, contagem in sorted(
                    contador.items(), key=lambda item: (-item[1], item[0])
                )[:limite]
            ]

        return {
            "bigramas": _ordenar(bigramas),
            "trigramas": _ordenar(trigramas),
        }

    # Faixas horárias espelham _stats_horarios: cada faixa cobre um intervalo de
    # horas e mapeia para um rótulo de perfil claro em PT-BR (R17.4). O mapeamento
    # é uma bijeção determinística faixa -> perfil:
    #   madrugada (00h-05h) -> "notívago"   (ativo na madrugada)
    #   manha     (06h-11h) -> "madrugador" (ativo de manhã cedo)
    #   tarde     (12h-17h) -> "vespertino" (ativo à tarde)
    #   noite     (18h-23h) -> "noturno"    (ativo à noite)
    # A ordem da tupla também define o desempate quando duas faixas têm a mesma
    # contagem: a primeira faixa listada vence.
    _FAIXAS_HORARIAS: tuple[tuple[str, range, str], ...] = (
        ("madrugada", range(0, 6), "notívago"),
        ("manha", range(6, 12), "madrugador"),
        ("tarde", range(12, 18), "vespertino"),
        ("noite", range(18, 24), "noturno"),
    )

    def _stats_linguistico(self, acc: _PassAccumulators) -> list[dict[str, Any]]:
        """Métricas linguísticas por participante (R17).

        Para cada participante calcula:

        - ``razao_pergunta_afirmacao`` (R17.1): razão entre mensagens de pergunta
          (corpo contendo ``?``) e mensagens de afirmação (demais). Quando não há
          afirmações, a razão equivale ao número de perguntas (divisão por 1);
          sem perguntas nem afirmações a razão é ``0.0``. Consideram-se apenas
          mensagens com corpo, ignorando chamadas e mensagens removidas (mesma
          regra de ``_stats_palavras``).
        - ``riqueza_vocabulario`` (R17.2): razão type-token (tokens únicos / total
          de tokens) sobre os tokens do participante, sempre em ``[0, 1]``; vale
          ``0.0`` quando o participante não possui tokens. A tokenização espelha
          ``_stats_palavras`` (minúsculas, divisão por espaços, pontuação das
          bordas removida), porém sem remover stop words, pois a métrica mede a
          diversidade de todo o vocabulário utilizado.
        - ``distribuicao_horaria`` (R17.3): contagem de mensagens datadas do
          participante por faixa horária (madrugada/manhã/tarde/noite). A soma
          das contagens iguala o número de mensagens datadas do participante.
        - ``perfil_horario`` (R17.4): rótulo derivado da faixa horária
          predominante (ver ``_FAIXAS_HORARIAS``); ``"indefinido"`` quando o
          participante não tem mensagens datadas.

        Retorna uma lista ordenada por nome do participante para determinismo.
        Um conjunto vazio reporta lista vazia sem erro.
        """
        # Acumuladores por participante, preenchidos na passagem única (R25).
        perguntas = acc.ling_perguntas
        afirmacoes = acc.ling_afirmacoes
        tokens_total = acc.ling_tokens_total
        tokens_unicos = acc.ling_tokens_unicos
        # Contagem por faixa horária: nome -> {faixa: contagem}.
        distrib = acc.ling_distrib
        # Conjunto de todos os participantes observados.
        participantes = acc.ling_participantes

        resultado: list[dict[str, Any]] = []
        for nome in participantes:
            n_perguntas = perguntas.get(nome, 0)
            n_afirmacoes = afirmacoes.get(nome, 0)
            # Divisão por 1 quando não há afirmações mantém a razão finita.
            razao = n_perguntas / n_afirmacoes if n_afirmacoes else float(n_perguntas)

            total_tok = tokens_total.get(nome, 0)
            riqueza = len(tokens_unicos[nome]) / total_tok if total_tok else 0.0

            # Distribuição completa com todas as faixas (zeradas quando ausentes).
            distribuicao = {
                faixa: distrib[nome].get(faixa, 0) for faixa, _, _ in self._FAIXAS_HORARIAS
            }

            # Faixa predominante define o perfil; desempate pela ordem das faixas.
            if any(distribuicao.values()):
                faixa_predominante = max(
                    self._FAIXAS_HORARIAS,
                    key=lambda item: distribuicao[item[0]],
                )
                perfil = faixa_predominante[2]
            else:
                perfil = "indefinido"

            resultado.append(
                {
                    "nome": nome,
                    "razao_pergunta_afirmacao": round(razao, 2),
                    "riqueza_vocabulario": round(riqueza, 4),
                    "distribuicao_horaria": distribuicao,
                    "perfil_horario": perfil,
                }
            )

        resultado.sort(key=lambda item: item["nome"])
        return resultado

    # Léxico local de sentimento em português (R18.1). Mantido embutido no
    # módulo para garantir operação 100% offline, sem qualquer chamada de rede
    # (R18.2). As palavras são armazenadas já normalizadas (minúsculas e sem
    # acentos) para casar com a tokenização normalizada usada em
    # ``_stats_sentimento``. As listas são propositalmente pequenas e focadas em
    # termos claramente carregados de tom, evitando palavras funcionais comuns
    # (como negações) que distorceriam a classificação.
    _LEXICO_POSITIVO: frozenset[str] = frozenset(
        {
            "bom",
            "boa",
            "otimo",
            "otima",
            "excelente",
            "maravilhoso",
            "maravilhosa",
            "amor",
            "amo",
            "adoro",
            "adorei",
            "feliz",
            "felicidade",
            "alegria",
            "legal",
            "gostei",
            "gosto",
            "lindo",
            "linda",
            "perfeito",
            "perfeita",
            "obrigado",
            "obrigada",
            "parabens",
            "bacana",
            "incrivel",
            "sucesso",
            "melhor",
            "otimas",
            "contente",
            "felizes",
            "abraco",
            "beijo",
            "sensacional",
        }
    )
    _LEXICO_NEGATIVO: frozenset[str] = frozenset(
        {
            "ruim",
            "pessimo",
            "pessima",
            "horrivel",
            "terrivel",
            "triste",
            "tristeza",
            "raiva",
            "odio",
            "odeio",
            "chato",
            "chata",
            "problema",
            "erro",
            "dificil",
            "cansado",
            "cansada",
            "medo",
            "droga",
            "idiota",
            "burro",
            "feio",
            "feia",
            "pior",
            "infelizmente",
            "doente",
            "briga",
            "chorar",
            "chateado",
            "chateada",
            "decepcionado",
            "decepcionada",
            "desastre",
            "fracasso",
        }
    )

    @staticmethod
    def _normalizar_token(palavra: str) -> str:
        """Normaliza um token para casamento com o léxico de sentimento.

        Converte para minúsculas, remove a pontuação das bordas (mesma regra de
        ``_stats_palavras``/``_stats_linguistico``) e remove os acentos via
        decomposição Unicode (NFKD), de modo que ``"ótimo"`` e ``"otimo"`` casem
        com a mesma entrada do léxico. Operação puramente local, sem rede.
        """
        limpo = palavra.lower().strip(".,!?;:()[]{}\"'…-_")
        if not limpo:
            return ""
        decomposto = unicodedata.normalize("NFKD", limpo)
        return "".join(ch for ch in decomposto if not unicodedata.combining(ch))

    def _stats_sentimento(self, acc: _PassAccumulators) -> list[dict[str, Any]]:
        """Análise de sentimento offline opcional por participante (R18).

        Este método só é invocado por ``generate_all`` quando
        ``config.sentiment_enabled`` é verdadeiro (R18.1, R18.3); caso contrário,
        a família ``sentimento`` é omitida da saída.

        A classificação é totalmente offline (R18.2): cada mensagem com corpo
        (ignorando chamadas e mensagens removidas, como em ``_stats_palavras``) é
        tokenizada e comparada contra um léxico local de termos positivos e
        negativos (:data:`_LEXICO_POSITIVO`/:data:`_LEXICO_NEGATIVO`). O tom da
        mensagem é:

        - ``"positivo"`` quando há mais acertos positivos que negativos;
        - ``"negativo"`` quando há mais acertos negativos que positivos;
        - ``"neutro"`` em empate (incluindo nenhum acerto).

        Reporta a distribuição de tom por participante (R18.4). Cada entrada
        expõe os campos do esquema (``nome``, ``distribuicao_tom``); o nome já
        vem redigido da Data_Layer (R4), como nos demais ``_stats_*``.
        ``distribuicao_tom`` traz as contagens absolutas por tom, o total
        classificado e as frações correspondentes (somando 1.0 quando há
        mensagens, ou 0.0 quando o participante não tem mensagens classificáveis).

        Retorna uma lista ordenada por nome para determinismo; conjunto vazio
        reporta lista vazia sem erro.
        """
        # Acumuladores por participante preenchidos na passagem única (R25):
        # nome -> Counter de tons; e conjunto de participantes observados.
        tons = acc.sent_tons
        participantes = acc.sent_participantes

        resultado: list[dict[str, Any]] = []
        for nome in participantes:
            contagem = tons[nome]
            positivo = contagem.get("positivo", 0)
            neutro = contagem.get("neutro", 0)
            negativo = contagem.get("negativo", 0)
            total = positivo + neutro + negativo

            if total:
                fracoes = {
                    "positivo": round(positivo / total, 4),
                    "neutro": round(neutro / total, 4),
                    "negativo": round(negativo / total, 4),
                }
            else:
                fracoes = {"positivo": 0.0, "neutro": 0.0, "negativo": 0.0}

            resultado.append(
                {
                    "nome": nome,
                    "distribuicao_tom": {
                        "positivo": positivo,
                        "neutro": neutro,
                        "negativo": negativo,
                        "total": total,
                        "fracoes": fracoes,
                    },
                }
            )

        resultado.sort(key=lambda item: item["nome"])
        return resultado

    _RE_EMOJI = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # símbolos e pictogramas
        "\U0001f680-\U0001f6ff"  # transporte e mapas
        "\U0001f1e0-\U0001f1ff"  # bandeiras
        "\U00002702-\U000027b0"  # dingbats
        "\U000024c2-\U0001f251"  # enclosed chars
        "\U0001f900-\U0001f9ff"  # suplementares
        "\U0001fa00-\U0001fa6f"  # chess, etc
        "\U0001fa70-\U0001faff"  # extras
        "\U00002600-\U000026ff"  # misc symbols
        "\U0000fe00-\U0000fe0f"  # variation selectors
        "\U0000200d"  # ZWJ
        "\U00002b50-\U00002b55"  # estrelas
        "\U0000231a-\U0000231b"  # watch/hourglass
        "\U00002934-\U00002935"  # setas
        "\U000025aa-\U000025ab"  # quadrados
        "\U000025fb-\U000025fe"  # quadrados
        "\U00002764"  # coração
        "]+",
        flags=re.UNICODE,
    )

    def _extract_emoji_clusters(self, text: str) -> list[str]:
        """Extrai clusters de emoji de um texto.

        Prefere a biblioteca opcional ``emoji`` quando disponível (cobertura
        Unicode mais ampla, R24.2); na ausência dela, recorre ao regex interno
        ``_RE_EMOJI`` sem interromper o cálculo (R24.3). Ambos os caminhos
        retornam os trechos de emoji encontrados, que são então decompostos em
        caracteres individuais por ``_stats_emojis`` (ignorando modificadores),
        produzindo resultados equivalentes em melhor esforço.
        """
        if EMOJI_AVAILABLE and emoji_lib is not None:
            return [match["emoji"] for match in emoji_lib.emoji_list(text)]
        return self._RE_EMOJI.findall(text)

    def _stats_emojis(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Estatísticas de emojis usados nas mensagens"""
        emoji_counter = acc.emoji_counter
        emoji_by_author = acc.emoji_by_author
        total_msgs_with_emoji = acc.emoji_msgs_com_emoji

        top_30 = emoji_counter.most_common(30)
        top_by_author = []
        for author, counter in sorted(
            emoji_by_author.items(), key=lambda x: sum(x[1].values()), reverse=True
        )[:10]:
            top_by_author.append(
                {
                    "nome": author,
                    "total": sum(counter.values()),
                    "top_3": [e for e, _ in counter.most_common(3)],
                }
            )

        return {
            "total_emojis": sum(emoji_counter.values()),
            "emojis_unicos": len(emoji_counter),
            "msgs_com_emoji": total_msgs_with_emoji,
            "top_30": [{"emoji": e, "contagem": c} for e, c in top_30],
            "por_autor": top_by_author,
        }

    def _stats_integridade_anexos(self, messages: list[Message]) -> dict[str, Any]:
        """Verifica integridade dos anexos (se os arquivos existem no disco)"""
        total = 0
        encontrados = 0
        faltando = 0
        faltando_lista: list[dict[str, Any]] = []

        for msg in messages:
            for att in msg.attachments:
                if not att.local_path:
                    continue
                total += 1

                # Tentar resolver caminho relativo a partir do base_dir de cada thread
                found = False
                check_path = Path(att.local_path)
                if check_path.is_absolute() and check_path.exists():
                    found = True
                elif self.base_dir:
                    full = self.base_dir / att.local_path
                    if full.exists():
                        found = True

                # Tentar a partir de base_dir dos threads
                if not found:
                    for t in self.threads:
                        if t.base_dir:
                            full = t.base_dir / att.local_path
                            if full.exists():
                                found = True
                                break

                if found:
                    encontrados += 1
                else:
                    faltando += 1
                    if len(faltando_lista) < 20:
                        faltando_lista.append(
                            {
                                "arquivo": att.filename,
                                "caminho": att.local_path,
                                "autor": msg.author,
                                "data": msg.sent.strftime("%d/%m/%Y") if msg.sent else "N/A",
                            }
                        )

        return {
            "total": total,
            "encontrados": encontrados,
            "faltando": faltando,
            "percentual_ok": round(encontrados / max(total, 1) * 100, 1),
            "faltando_lista": faltando_lista,
        }

    def _stats_gaps(self, min_days: int = 30) -> dict[str, Any]:
        """Detecta períodos de inatividade (gaps) maiores que min_days em cada conversa"""
        all_gaps = []

        for thread in self.threads:
            dates = sorted([m.sent for m in thread.messages if m.sent])
            if len(dates) < 2:
                continue

            for i in range(1, len(dates)):
                delta = dates[i] - dates[i - 1]
                if delta.days >= min_days:
                    all_gaps.append(
                        {
                            "conversa": thread.thread_name or "Sem nome",
                            "de": dates[i - 1].strftime("%d/%m/%Y"),
                            "ate": dates[i].strftime("%d/%m/%Y"),
                            "dias": delta.days,
                        }
                    )

        # Ordenar por duração (maior primeiro)
        all_gaps.sort(key=lambda g: g["dias"], reverse=True)

        # Estatísticas gerais
        total_gaps = len(all_gaps)
        conversas_com_gaps = len({g["conversa"] for g in all_gaps})
        maior_gap = all_gaps[0] if all_gaps else None

        return {
            "total_gaps": total_gaps,
            "conversas_com_gaps": conversas_com_gaps,
            "maior_gap": maior_gap,
            "min_dias": min_days,
            "gaps": all_gaps[:50],  # Limitar a 50 maiores
        }

    def _grafo_data(self, max_nodes: int = 30) -> dict[str, Any]:
        """Dados estruturais do grafo de relacionamentos entre participantes (R26).

        Produz apenas a *estrutura* do grafo (nós e arestas), sem qualquer
        marcação SVG (R26.1). A renderização visual é responsabilidade da camada
        de apresentação (``StatsReportRenderer.render_graph_svg``), que deriva o
        SVG exclusivamente destes dados (R26.2). O formato é estruturado e
        adequado para exportação em JSON/CSV (R26.3), usando exatamente os campos
        declarados no esquema compartilhado (``advanced_stats_schema``):
        ``nodes`` e ``edges``.

        - ``nodes``: lista de ``{"nome": <participante>, "peso": <nº de mensagens>}``
          limitada aos ``max_nodes`` participantes de maior peso (ordem
          decrescente). Os nomes já vêm redigidos da Data_Layer, consistente com
          as demais métricas.
        - ``edges``: lista de ``{"a": <nó>, "b": <nó>, "peso": <co-ocorrência>}``
          contendo apenas arestas cujos dois extremos estão entre os nós do topo.

        Um conjunto sem mensagens (ou sem participantes) produz ``nodes`` e
        ``edges`` vazios, sem erro.
        """
        # Contar mensagens entre pares de participantes (co-ocorrência em threads)
        pair_counts: Counter[tuple[str, str]] = Counter()
        node_counts: Counter[str] = Counter()

        for thread in self.threads:
            names = sorted({p[0] for p in thread.participants})
            msg_count = len(thread.messages)
            if msg_count == 0:
                continue

            for name in names:
                node_counts[name] += msg_count

            # Gerar pares (co-ocorrência = compartilham a mesma conversa)
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pair_counts[(names[i], names[j])] += msg_count

        if not node_counts:
            return {"nodes": [], "edges": []}

        # Limitar aos top N participantes por mensagens (ordem decrescente).
        top_nodes = [n for n, _ in node_counts.most_common(max_nodes)]
        top_set = set(top_nodes)

        nodes = [{"nome": name, "peso": node_counts[name]} for name in top_nodes]

        # Filtrar pares com apenas nós do top.
        edges = [
            {"a": a, "b": b, "peso": weight}
            for (a, b), weight in pair_counts.items()
            if a in top_set and b in top_set
        ]

        return {"nodes": nodes, "edges": edges}

    # Faixas de tamanho (em caracteres) para o histograma de tamanho de
    # mensagens. Definidas como constante de classe para serem compartilhadas
    # entre a passagem única (R25) e a finalização, garantindo rótulos e limites
    # idênticos à implementação original.
    _TAMANHO_FAIXAS: tuple[tuple[int, float, str], ...] = (
        (0, 10, "0-10"),
        (11, 50, "11-50"),
        (51, 150, "51-150"),
        (151, 500, "151-500"),
        (501, 1000, "501-1000"),
        (1001, float("inf"), "1000+"),
    )

    def _stats_tamanho_mensagens(self, acc: _PassAccumulators) -> dict[str, Any]:
        """Distribuição de tamanho de mensagens (histograma por faixas de caracteres)"""
        faixas = self._TAMANHO_FAIXAS

        # Distribuição geral
        dist_geral = acc.tamanho_dist_geral
        # Por participante (top 10)
        dist_por_autor = acc.tamanho_dist_por_autor
        total_chars = acc.tamanho_total_chars
        total_msgs_com_texto = acc.tamanho_total_msgs_com_texto

        # Top autores por volume
        author_totals: Counter[str] = Counter()
        for author, counts in dist_por_autor.items():
            author_totals[author] = sum(counts.values())
        top_authors = [a for a, _ in author_totals.most_common(8)]

        media_chars = round(total_chars / max(total_msgs_com_texto, 1), 1)

        return {
            "distribuicao": {label: dist_geral.get(label, 0) for _, _, label in faixas},
            "faixas": [label for _, _, label in faixas],
            "por_autor": {
                a: {label: dist_por_autor[a].get(label, 0) for _, _, label in faixas}
                for a in top_authors
            },
            "media_chars": media_chars,
            "total_msgs_com_texto": total_msgs_com_texto,
        }

    def _stats_comparacao_periodos(self, messages: list[Message]) -> dict[str, Any]:
        """Compara métricas entre primeira e segunda metade do período total"""
        dated = [m for m in messages if m.sent]
        if len(dated) < 2:
            return {"ativo": False}

        dates = sorted(m.sent for m in dated)
        mid_date = dates[len(dates) // 2]
        first_date = dates[0]
        last_date = dates[-1]

        p1 = [m for m in dated if m.sent < mid_date]
        p2 = [m for m in dated if m.sent >= mid_date]

        def _metrics(msgs):
            total = len(msgs)
            anexos = sum(len(m.attachments) for m in msgs)
            chamadas = sum(1 for m in msgs if m.is_call)
            chars = sum(len(m.body) for m in msgs if m.body)
            autores = len({m.author for m in msgs})
            media_len = round(chars / max(total, 1), 1)
            return {
                "msgs": total,
                "anexos": anexos,
                "chamadas": chamadas,
                "chars": chars,
                "autores": autores,
                "media_len": media_len,
            }

        m1 = _metrics(p1)
        m2 = _metrics(p2)

        def _variacao(v1, v2):
            if v1 == 0:
                return "+100%" if v2 > 0 else "0%"
            pct = round((v2 - v1) / v1 * 100, 1)
            return f"{pct:+.1f}%"

        return {
            "ativo": True,
            "p1_de": first_date.strftime("%d/%m/%Y"),
            "p1_ate": (mid_date - timedelta(days=1)).strftime("%d/%m/%Y"),
            "p2_de": mid_date.strftime("%d/%m/%Y"),
            "p2_ate": last_date.strftime("%d/%m/%Y"),
            "p1": m1,
            "p2": m2,
            "variacoes": {
                "msgs": _variacao(m1["msgs"], m2["msgs"]),
                "anexos": _variacao(m1["anexos"], m2["anexos"]),
                "chamadas": _variacao(m1["chamadas"], m2["chamadas"]),
                "autores": _variacao(m1["autores"], m2["autores"]),
                "media_len": _variacao(m1["media_len"], m2["media_len"]),
            },
        }

    def _normalize_language_text(self, text: str) -> str:
        """Normaliza texto para detecção de idioma."""
        normalized = re.sub(r"\s+", " ", (text or "").strip())
        return normalized[: self._LANG_CHUNK_TARGET]

    def _build_language_chunks(self, messages: list[Message]) -> list[str]:
        """Agrupa mensagens em chunks maiores para melhorar a acurácia do detector."""
        chunks: list[str] = []
        current_parts: list[str] = []
        current_size = 0
        processed = 0

        for msg in messages:
            if processed >= self._LANG_MESSAGE_LIMIT or len(chunks) >= self._LANG_MAX_CHUNKS:
                break
            if not msg.body:
                continue

            text = self._normalize_language_text(msg.body)
            if len(text) < self._LANG_MIN_CHARS:
                continue

            processed += 1
            if current_parts and current_size + len(text) + 1 > self._LANG_CHUNK_TARGET:
                chunks.append(" ".join(current_parts))
                current_parts = []
                current_size = 0
                if len(chunks) >= self._LANG_MAX_CHUNKS:
                    break

            current_parts.append(text)
            current_size += len(text) + 1

        if current_parts and len(chunks) < self._LANG_MAX_CHUNKS:
            chunks.append(" ".join(current_parts))

        return chunks

    def _stats_idiomas_keywords(self, messages: list[Message]) -> dict[str, Any]:
        """Fallback simples baseado em palavras-chave quando langdetect não está disponível."""
        word_counter: Counter[str] = Counter()

        for msg in messages:
            if not msg.body or len(msg.body) < 10:
                continue
            words = set(msg.body.lower().split())
            for word in words:
                if len(word) >= 2:
                    word_counter[word] += 1

        lang_scores: dict[str, int] = {}
        for lang, keywords in self._LANG_KEYWORDS.items():
            score = sum(word_counter.get(keyword, 0) for keyword in keywords)
            lang_scores[lang] = score

        total_score = sum(lang_scores.values())
        if total_score == 0:
            return {
                "principal": "Indeterminado",
                "percentuais": {},
                "scores": {},
                "metodo": "keywords",
            }

        percentuais = {
            lang: round(score / total_score * 100, 1)
            for lang, score in sorted(lang_scores.items(), key=lambda item: item[1], reverse=True)
            if score > 0
        }
        principal = max(lang_scores, key=lambda lang: lang_scores[lang])

        return {
            "principal": principal,
            "percentuais": percentuais,
            "scores": lang_scores,
            "metodo": "keywords",
        }

    def _stats_idiomas_langdetect(self, messages: list[Message]) -> dict[str, Any] | None:
        """Tenta detectar idioma com langdetect, se disponível."""
        if not LANGDETECT_AVAILABLE or detect_langs is None:
            return None

        chunks = self._build_language_chunks(messages)
        if not chunks:
            return None

        lang_scores: defaultdict[str, float] = defaultdict(float)
        analyzed_chunks = 0

        for chunk in chunks:
            try:
                detections = detect_langs(chunk)
            except LangDetectException:
                continue

            for detection in detections:
                lang_code = detection.lang.lower()
                # R24.1: quando o código detectado não está no mapa de exibição,
                # reportamos o idioma pelo próprio código em vez de descartá-lo.
                lang_name = self._LANG_CODE_MAP.get(lang_code, lang_code)
                lang_scores[lang_name] += detection.prob
            analyzed_chunks += 1

        total_score = sum(lang_scores.values())
        if analyzed_chunks == 0 or total_score == 0:
            return None

        percentuais = {
            lang: round(score / total_score * 100, 1)
            for lang, score in sorted(lang_scores.items(), key=lambda item: item[1], reverse=True)
            if score > 0
        }
        principal = max(lang_scores, key=lambda lang: lang_scores[lang])

        return {
            "principal": principal,
            "percentuais": percentuais,
            "scores": {lang: round(score, 4) for lang, score in lang_scores.items()},
            "metodo": "langdetect",
            "amostras_analisadas": analyzed_chunks,
        }

    def _stats_idiomas(self, messages: list[Message]) -> dict[str, Any]:
        """Detecta idiomas predominantes, usando langdetect quando disponível."""
        detected = self._stats_idiomas_langdetect(messages)
        if detected:
            return detected
        return self._stats_idiomas_keywords(messages)

    def _stats_timeline(self) -> list[dict[str, Any]]:
        """Gera dados de timeline para cada conversa (início, fim, volume)"""
        timeline = []
        for t in self.threads:
            dates = [m.sent for m in t.messages if m.sent]
            if not dates:
                continue
            first = min(dates)
            last = max(dates)
            name = t.thread_name or (t.participants[0].username if t.participants else t.thread_id)
            timeline.append(
                {
                    "name": name,
                    "start": first,
                    "end": last,
                    "count": len(t.messages),
                }
            )
        timeline.sort(key=lambda x: x["start"])
        return timeline

    def generate_html_report(self) -> str:
        """Gera um relatório HTML completo com gráficos CSS"""
        return StatsReportRenderer.render_html_report(self.generate_all())

    @staticmethod
    def get_stats_css() -> str:
        """Retorna CSS para o painel de estatísticas"""
        return StatsReportRenderer.get_stats_css()

    @staticmethod
    def get_stats_js() -> str:
        """Retorna JavaScript para o painel de estatísticas"""
        return StatsReportRenderer.get_stats_js()
