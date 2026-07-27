"""
Meta Platforms Chat Exporter - Motor de redação centralizado

Aplica a redação de dados sensíveis diretamente na Data_Layer (lista de `Thread`
e `ProfileMedia`), uma única vez, antes de qualquer exportação. Centraliza a
lógica que antes vivia em `AllChatsHTMLGenerator._apply_redaction`, para que
todos os formatos (HTML unificado, HTML individual, JSON, CSV e relatório de
estatísticas) consumam dados já redigidos de forma consistente.

A redação é aplicada **in-place** e é **idempotente**: reaplicar a redação
(mesmo com uma nova instância) não corrompe os aliases já atribuídos nem os
demais campos já redigidos.

Regras de redação:
- Nomes de usuários (autores, participantes, ex-participantes) viram aliases
  estáveis "Participante N"; o próprio dono vira "Você".
- Identificadores de usuário (`user_id`/`author_id`) são removidos.
- Números longos (>= 8 dígitos) em textos viram "[REDIGIDO]".
- Nomes de conversas viram "Conversa Redigida".
- Caminhos de arquivos de anexos exibidos (filename/local_path) têm os números
  longos ocultados, redigindo os caminhos mostrados na seção de integridade
  de anexos (R4.6).
- ``share_url`` tem sequências de 8+ dígitos ocultadas (IDs embutidos).
- ``subscription_users`` recebe os mesmos aliases estáveis dos participantes.
"""

import re

from meta_chat_exporter.models import ProfileMedia, Thread

# Texto usado para substituir números longos (IDs, telefones)
REDACTED_TOKEN = "[REDIGIDO]"
# Nome fixo atribuído a conversas redigidas
REDACTED_THREAD_NAME = "Conversa Redigida"
# Alias atribuído ao próprio dono da exportação
OWNER_ALIAS = "Você"

# Números com 8 ou mais dígitos (IDs internos, telefones, etc.) em textos livres
_NUM_RE = re.compile(r"\b\d{8,}\b")
# Em caminhos de arquivos os IDs costumam vir embutidos (ex.: "IMG_12345678.jpg"),
# então qualquer sequência de 8+ dígitos é ocultada, sem exigir limites de palavra.
_PATH_NUM_RE = re.compile(r"\d{8,}")
# Reconhece aliases já atribuídos, para garantir idempotência
_ALIAS_RE = re.compile(r"^Participante \d+$")


class RedactionEngine:
    """Redige dados sensíveis na Data_Layer, in-place e de forma idempotente."""

    def __init__(self, owner_username: str):
        self.owner_username = owner_username or ""
        # Mapping estável: nome original → "Participante N"
        self._aliases: dict[str, str] = {}
        self._next_id = 1

    def redact(self, threads: list[Thread], profile_media: ProfileMedia | None = None) -> None:
        """Aplica a redação in-place sobre os threads (e, futuramente, mídias de
        perfil). Pode ser chamado mais de uma vez sem corromper os aliases."""
        for thread in threads:
            self._redact_thread(thread)
        # `profile_media` faz parte do contrato (R4) para que o ponto único de
        # redação receba toda a Data_Layer. As mídias de perfil não alimentam a
        # seção de integridade de anexos nem expõem nomes de participantes, por
        # isso não há campos a redigir aqui no momento.
        _ = profile_media

    def _get_alias(self, name: str) -> str:
        """Retorna o alias estável para um nome de usuário.

        Idempotente: nomes vazios, o próprio dono, o alias do dono ("Você") e
        aliases já atribuídos ("Participante N") são preservados como estão.
        """
        if not name or name == self.owner_username or name == OWNER_ALIAS:
            return OWNER_ALIAS
        if _ALIAS_RE.match(name):
            # Já redigido em uma passagem anterior — preserva o alias existente
            return name
        if name in self._aliases:
            return self._aliases[name]
        alias = f"Participante {self._next_id}"
        self._next_id += 1
        self._aliases[name] = alias
        return alias

    def _redact_thread(self, thread: Thread) -> None:
        """Redige um único thread in-place."""
        # Nome da conversa
        if thread.thread_name:
            thread.thread_name = REDACTED_THREAD_NAME

        # Participantes atuais
        thread.participants = [
            p._replace(username=self._get_alias(p.username), user_id="")
            for p in thread.participants
        ]

        # Ex-participantes (mantém robustez caso não seja um Participant)
        new_past = []
        for p in thread.past_participants:
            name = p.username if hasattr(p, "username") else str(p)
            new_past.append(p._replace(username=self._get_alias(name), user_id=""))
        thread.past_participants = new_past

        # Mensagens
        for msg in thread.messages:
            msg.author = self._get_alias(msg.author)
            msg.author_id = ""
            if msg.body:
                msg.body = _NUM_RE.sub(REDACTED_TOKEN, msg.body)
            if msg.share_text:
                msg.share_text = _NUM_RE.sub(REDACTED_TOKEN, msg.share_text)
            if msg.share_url:
                # Números longos em URLs (IDs embutidos) e schemes já filtrados no HTML
                msg.share_url = _PATH_NUM_RE.sub(REDACTED_TOKEN, msg.share_url)
            if msg.subscription_users:
                msg.subscription_users = [
                    self._get_alias(u) for u in msg.subscription_users if u
                ]
            # R4.6 — redige os caminhos de anexos exibidos (seção de integridade)
            for att in msg.attachments:
                if att.filename:
                    att.filename = _PATH_NUM_RE.sub(REDACTED_TOKEN, att.filename)
                if att.local_path:
                    att.local_path = _PATH_NUM_RE.sub(REDACTED_TOKEN, att.local_path)
