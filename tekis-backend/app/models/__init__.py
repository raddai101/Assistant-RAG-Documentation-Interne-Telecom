"""
Point d'entrée unique pour les modèles SQLAlchemy. Importer ce module garantit que
tous les modèles sont enregistrés auprès de `db.metadata` avant `create_all()` ou une
migration Alembic.
"""
from app.models.identity import Department, Role, User  # noqa: F401
from app.models.document import Document, DocumentVersion, Permission, DocumentStatus  # noqa: F401
from app.models.chunk import Chunk, ChunkEmbeddingMeta  # noqa: F401
from app.models.audit import AuditLog, Session, Feedback  # noqa: F401
from app.models.conversation import Conversation, ChatMessage  # noqa: F401

__all__ = [
    "Department",
    "Role",
    "User",
    "Document",
    "DocumentVersion",
    "Permission",
    "DocumentStatus",
    "Chunk",
    "ChunkEmbeddingMeta",
    "AuditLog",
    "Session",
    "Feedback",
    "Conversation",
    "ChatMessage",
]
