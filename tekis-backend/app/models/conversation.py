"""
Modèles de conversations persistantes de TEKIS.

Une conversation appartient à un utilisateur et contient des messages ordonnés.
Les conversations servent à la fois de mémoire conversationnelle et d'historique.
"""
from datetime import datetime, timezone

from app.extensions import db


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    user = db.relationship("User", backref=db.backref("conversations", lazy="dynamic"))
    messages = db.relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self):
        return f"<Conversation {self.id} user={self.user_id} title={self.title!r}>"


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    conversation = db.relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<ChatMessage {self.id} conversation={self.conversation_id} role={self.role}>"
