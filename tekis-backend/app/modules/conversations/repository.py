from datetime import datetime, timezone

from app.extensions import db
from app.models.conversation import Conversation, ChatMessage


class ConversationRepository:
    """Accès PostgreSQL aux conversations. Chaque méthode utilise la session Flask courante."""

    def create(self, user_id: int, title: str) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        db.session.add(conversation)
        db.session.flush()
        return conversation

    def get_owned(self, conversation_id: int, user_id: int) -> Conversation | None:
        return (
            db.session.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .first()
        )

    def list_owned(self, user_id: int) -> list[Conversation]:
        return (
            db.session.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .all()
        )

    def list_messages(self, conversation_id: int, user_id: int, limit: int = 30) -> list[ChatMessage]:
        conversation = self.get_owned(conversation_id, user_id)
        if conversation is None:
            return []
        return (
            db.session.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
            .all()
        )[::-1]

    def add_message(self, conversation: Conversation, role: str, content: str) -> ChatMessage:
        message = ChatMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
        )
        db.session.add(message)
        conversation.updated_at = datetime.now(timezone.utc)
        db.session.flush()
        return message

    def delete(self, conversation: Conversation) -> None:
        db.session.delete(conversation)
