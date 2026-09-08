"""
Modèle Chunk (module `ingestion` / `knowledge`).

Rappel décision §6.2 du memoire.md : les vecteurs eux-mêmes sont stockés dans
ChromaDB, jamais dans PostgreSQL. `ChunkEmbeddingMeta` ne conserve que la métadonnée
relationnelle (quel chunk, quel modèle d'embedding, quelle dimension) permettant de
retrouver le vecteur correspondant côté ChromaDB — l'accès au vecteur lui-même passe
exclusivement par le `VectorStoreContract` (module retrieval, à partir de la Phase 2).
"""
from datetime import datetime, timezone

from app.extensions import db


class Chunk(db.Model):
    __tablename__ = "chunks"

    id = db.Column(db.Integer, primary_key=True)
    document_version_id = db.Column(
        db.Integer, db.ForeignKey("document_versions.id"), nullable=False
    )
    section = db.Column(db.String(255), nullable=True)
    page = db.Column(db.Integer, nullable=True)
    content = db.Column(db.Text, nullable=False)
    position = db.Column(db.Integer, nullable=False)
    content_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    document_version = db.relationship("DocumentVersion", back_populates="chunks")
    embedding_meta = db.relationship(
        "ChunkEmbeddingMeta",
        back_populates="chunk",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Chunk {self.id} dv={self.document_version_id} pos={self.position}>"


class ChunkEmbeddingMeta(db.Model):
    """Métadonnée du vecteur d'un chunk. Le vecteur lui-même vit dans ChromaDB."""

    __tablename__ = "chunk_embeddings"

    chunk_id = db.Column(db.Integer, db.ForeignKey("chunks.id"), primary_key=True)
    embedding_model = db.Column(db.String(100), nullable=False)
    dimension = db.Column(db.Integer, nullable=False)
    chroma_id = db.Column(db.String(150), nullable=True)  # id du vecteur dans ChromaDB
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    chunk = db.relationship("Chunk", back_populates="embedding_meta")

    def __repr__(self):
        return f"<ChunkEmbeddingMeta chunk={self.chunk_id} model={self.embedding_model}>"
