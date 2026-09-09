from concurrent.futures import ThreadPoolExecutor
import logging
import re

from flask import Flask

from app.extensions import db
from app.models.conversation import Conversation
from app.modules.conversations.repository import ConversationRepository

logger = logging.getLogger(__name__)

# Les écritures secondaires (réponse assistant) ne bloquent pas le streaming.
_PERSIST_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="tekis-memory")


def make_title(first_message: str, max_length: int = 70) -> str:
    """Titre court déterministe à partir du premier message utilisateur."""
    text = re.sub(r"\s+", " ", (first_message or "")).strip()
    if not text:
        return "Nouvelle discussion"
    # Première phrase, ou première ligne si le message n'a pas de ponctuation.
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0].strip()
    if len(sentence) > max_length:
        sentence = sentence[:max_length].rsplit(" ", 1)[0].rstrip(" ,;:-")
        sentence += "…"
    return sentence or "Nouvelle discussion"


class ConversationService:
    def __init__(self, repository: ConversationRepository | None = None):
        self.repository = repository or ConversationRepository()

    def create_for_first_message(self, user_id: int, first_message: str) -> Conversation:
        conversation = self.repository.create(user_id, make_title(first_message))
        self.repository.add_message(conversation, "user", first_message)
        db.session.commit()
        return conversation

    def ensure_owned(self, conversation_id: int, user_id: int) -> Conversation | None:
        return self.repository.get_owned(conversation_id, user_id)

    def add_user_message(self, conversation: Conversation, content: str) -> None:
        self.repository.add_message(conversation, "user", content)
        db.session.commit()

    def recent_messages(self, conversation_id: int, user_id: int, limit: int = 12) -> list[dict]:
        messages = self.repository.list_messages(conversation_id, user_id, limit=limit)
        return [{"role": m.role, "content": m.content} for m in messages]

    def list_for_user(self, user_id: int) -> list[Conversation]:
        return self.repository.list_owned(user_id)

    def delete_owned(self, conversation_id: int, user_id: int) -> bool:
        conversation = self.repository.get_owned(conversation_id, user_id)
        if conversation is None:
            return False
        self.repository.delete(conversation)
        db.session.commit()
        return True

    def persist_assistant_async(
        self,
        app: Flask,
        conversation_id: int,
        user_id: int,
        content: str,
    ) -> None:
        # Une session SQLAlchemy Flask est locale au thread : on crée donc un
        # contexte Flask dans le worker et on utilise sa session dédiée.
        _PERSIST_EXECUTOR.submit(
            _persist_assistant_message,
            app,
            conversation_id,
            user_id,
            content,
        )


def _persist_assistant_message(
    app: Flask,
    conversation_id: int,
    user_id: int,
    content: str,
) -> None:
    with app.app_context():
        try:
            repo = ConversationRepository()
            conversation = repo.get_owned(conversation_id, user_id)
            if conversation is None:
                logger.warning(
                    "[MEMORY] conversation %s introuvable pour user %s",
                    conversation_id,
                    user_id,
                )
                return
            repo.add_message(conversation, "assistant", content)
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception("[MEMORY] échec de persistance du message assistant")
        finally:
            db.session.remove()
