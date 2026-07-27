"""
Testes para o motor de redação centralizado (`redaction.py`).
"""

import os
import sys
import unittest
from datetime import datetime

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta_chat_exporter.models import Attachment, Message, Participant, ProfileMedia, Thread
from meta_chat_exporter.redaction import (
    OWNER_ALIAS,
    REDACTED_THREAD_NAME,
    REDACTED_TOKEN,
    RedactionEngine,
)


def _make_msg(author="friend", author_id="200", body="", attachments=None, share_text=None):
    return Message(
        author=author,
        author_id=author_id,
        platform="instagram",
        sent=datetime(2024, 1, 15, 10, 0, 0),
        body=body,
        attachments=attachments or [],
        share_text=share_text,
    )


def _make_thread():
    return Thread(
        thread_id="t1",
        thread_name="Conversa com Amigos",
        participants=[
            Participant("owner", "instagram", "100"),
            Participant("friend", "instagram", "200"),
        ],
        past_participants=[Participant("oldfriend", "instagram", "300")],
        messages=[
            _make_msg(author="owner", author_id="100", body="Meu numero e 11987654321"),
            _make_msg(
                author="friend",
                author_id="200",
                body="Ok!",
                share_text="ligue 5551234567 agora",
                attachments=[
                    Attachment(
                        filename="IMG_12345678.jpg",
                        file_type="image/jpeg",
                        local_path="media/IMG_12345678.jpg",
                    )
                ],
            ),
        ],
    )


class TestRedactionEngine(unittest.TestCase):
    def test_redige_nome_da_conversa(self):
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        self.assertEqual(thread.thread_name, REDACTED_THREAD_NAME)

    def test_dono_vira_voce(self):
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        # O dono ("owner") deve virar "Você" em participantes e mensagens
        self.assertIn(OWNER_ALIAS, [p.username for p in thread.participants])
        self.assertEqual(thread.messages[0].author, OWNER_ALIAS)

    def test_participantes_viram_alias(self):
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        usernames = [p.username for p in thread.participants]
        self.assertIn("Participante 1", usernames)
        # user_id removido
        for p in thread.participants:
            self.assertEqual(p.user_id, "")

    def test_ex_participantes_viram_alias(self):
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        self.assertEqual(thread.past_participants[0].user_id, "")
        self.assertTrue(thread.past_participants[0].username.startswith("Participante"))

    def test_numeros_longos_ocultados_no_body(self):
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        self.assertIn(REDACTED_TOKEN, thread.messages[0].body)
        self.assertNotIn("11987654321", thread.messages[0].body)

    def test_numeros_longos_ocultados_no_share_text(self):
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        self.assertIn(REDACTED_TOKEN, thread.messages[1].share_text)
        self.assertNotIn("5551234567", thread.messages[1].share_text)

    def test_author_id_removido(self):
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        for msg in thread.messages:
            self.assertEqual(msg.author_id, "")

    def test_caminhos_de_anexos_redigidos(self):
        """R4.6 — números longos nos caminhos exibidos são ocultados."""
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        att = thread.messages[1].attachments[0]
        self.assertNotIn("12345678", att.filename)
        self.assertNotIn("12345678", att.local_path)
        self.assertIn(REDACTED_TOKEN, att.filename)
        self.assertIn(REDACTED_TOKEN, att.local_path)

    def test_numeros_curtos_preservados(self):
        thread = Thread(
            thread_id="t",
            thread_name="x",
            participants=[Participant("friend", "instagram", "200")],
            messages=[_make_msg(author="friend", body="encontro as 1234")],
        )
        RedactionEngine("owner").redact([thread])
        self.assertIn("1234", thread.messages[0].body)

    def test_idempotente_nova_instancia(self):
        """Reaplicar a redação (nova instância) não corrompe aliases."""
        thread = _make_thread()
        RedactionEngine("owner").redact([thread])
        snapshot_usernames = [p.username for p in thread.participants]
        snapshot_authors = [m.author for m in thread.messages]
        snapshot_name = thread.thread_name
        snapshot_body = [m.body for m in thread.messages]

        # Segunda aplicação com nova instância
        RedactionEngine("owner").redact([thread])
        self.assertEqual([p.username for p in thread.participants], snapshot_usernames)
        self.assertEqual([m.author for m in thread.messages], snapshot_authors)
        self.assertEqual(thread.thread_name, snapshot_name)
        self.assertEqual([m.body for m in thread.messages], snapshot_body)

    def test_idempotente_mesma_instancia(self):
        thread = _make_thread()
        engine = RedactionEngine("owner")
        engine.redact([thread])
        first = [p.username for p in thread.participants]
        engine.redact([thread])
        self.assertEqual([p.username for p in thread.participants], first)

    def test_aliases_estaveis_entre_threads(self):
        """O mesmo nome em threads diferentes recebe o mesmo alias."""
        t1 = Thread(
            thread_id="1",
            thread_name="",
            participants=[Participant("alice", "instagram", "1")],
            messages=[_make_msg(author="alice", author_id="1")],
        )
        t2 = Thread(
            thread_id="2",
            thread_name="",
            participants=[Participant("alice", "instagram", "1")],
            messages=[_make_msg(author="alice", author_id="1")],
        )
        RedactionEngine("owner").redact([t1, t2])
        self.assertEqual(t1.messages[0].author, t2.messages[0].author)

    def test_aceita_profile_media(self):
        thread = _make_thread()
        # Não deve lançar exceção ao receber profile_media
        RedactionEngine("owner").redact([thread], ProfileMedia())

    def test_share_url_numeros_longos_redigidos(self):
        thread = Thread(
            thread_id="t",
            thread_name="x",
            participants=[Participant("friend", "instagram", "200")],
            messages=[
                Message(
                    author="friend",
                    author_id="200",
                    platform="instagram",
                    body="link",
                    share_url="https://instagram.com/p/ABC12345678XYZ",
                )
            ],
        )
        RedactionEngine("owner").redact([thread])
        self.assertNotIn("12345678", thread.messages[0].share_url)
        self.assertIn(REDACTED_TOKEN, thread.messages[0].share_url)

    def test_subscription_users_viram_alias(self):
        thread = Thread(
            thread_id="t",
            thread_name="grupo",
            participants=[
                Participant("owner", "instagram", "100"),
                Participant("alice", "instagram", "1"),
            ],
            messages=[
                Message(
                    author="owner",
                    author_id="100",
                    platform="instagram",
                    body="",
                    subscription_event="subscribe",
                    subscription_users=["alice", "bob"],
                )
            ],
        )
        RedactionEngine("owner").redact([thread])
        users = thread.messages[0].subscription_users
        self.assertTrue(all(u.startswith("Participante") or u == OWNER_ALIAS for u in users))
        self.assertNotIn("alice", users)
        self.assertNotIn("bob", users)

    def test_metricas_a1_a2_a4_sem_nomes_reais_apos_redacao(self):
        """Após redação, generate_all não deve expor usernames originais em A1/A2/A4."""
        from meta_chat_exporter.stats import ChatStatistics

        thread = Thread(
            thread_id="dm1",
            thread_name="Chat secreto",
            participants=[
                Participant("owner", "instagram", "100"),
                Participant("suspect", "instagram", "200"),
            ],
            messages=[
                Message(
                    author="owner",
                    author_id="100",
                    platform="instagram",
                    sent=datetime(2024, 1, 1, 2, 0, 0),
                    body="oi",
                ),
                Message(
                    author="suspect",
                    author_id="200",
                    platform="instagram",
                    sent=datetime(2024, 1, 1, 2, 5, 0),
                    body="ola",
                ),
            ],
        )
        RedactionEngine("owner").redact([thread])
        stats = ChatStatistics([thread], owner_username=OWNER_ALIAS).generate_all()
        blob = str(stats.get("timeline_contatos")) + str(stats.get("atividade_noturna")) + str(
            stats.get("taxa_resposta")
        )
        self.assertNotIn("suspect", blob)
        self.assertNotIn("Chat secreto", blob)


if __name__ == "__main__":
    unittest.main()
