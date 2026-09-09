"""
Repository du module `retrieval`. Séparé de `IngestionRepository` (Phase 1, ne pas
toucher — phase déjà close et testée) : c'est le module `retrieval` qui possède la
logique d'indexation vectorielle, conformément à l'isolation des accès DB (§9) et à
la frontière `retrieval-service` définie en Phase 0 (memoire.md §5).
"""
from app.extensions import db
from app.models.chunk import Chunk, ChunkEmbeddingMeta
from app.models.document import Document, DocumentVersion

class RetrievalRepository:
    def get_chunks_without_embedding(
        self, document_version_id: int | None = None
    ) -> list[Chunk]:
        """Renvoie les chunks n'ayant pas encore de métadonnée d'embedding
        (`chunk_embeddings.chunk_id` absent), optionnellement filtrés sur une
        version de document précise."""
        query = (
            db.session.query(Chunk)
            .outerjoin(ChunkEmbeddingMeta, ChunkEmbeddingMeta.chunk_id == Chunk.id)
            .filter(ChunkEmbeddingMeta.chunk_id.is_(None))
        )
        if document_version_id is not None:
            query = query.filter(Chunk.document_version_id == document_version_id)
        return query.order_by(Chunk.id).all()

    def save_embedding_meta(
        self, chunk: Chunk, embedding_model: str, dimension: int, chroma_id: str
    ) -> ChunkEmbeddingMeta:
        meta = db.session.get(ChunkEmbeddingMeta, chunk.id)
        if meta is None:
            meta = ChunkEmbeddingMeta(chunk_id=chunk.id)
            db.session.add(meta)
        meta.embedding_model = embedding_model
        meta.dimension = dimension
        meta.chroma_id = chroma_id
        db.session.flush()
        return meta

    def get_document_version(self, document_version_id: int) -> DocumentVersion | None:
        return db.session.get(DocumentVersion, document_version_id)

    def get_source_metadata(self, chunk_ids: list[int]) -> dict[int, dict]:
        """Retourne les métadonnées documentaires lisibles pour un ensemble de chunks.

        Le chunk_id reste un identifiant technique interne au retrieval. La couche API
        expose ensuite le titre/nom du document et sa version à l'utilisateur.
        Une seule requête SQL est utilisée pour éviter un N+1 lors de chaque réponse.
        """
        if not chunk_ids:
            return {}

        rows = (
            db.session.query(
                Chunk.id.label("chunk_id"),
                DocumentVersion.id.label("document_version_id"),
                DocumentVersion.version.label("version"),
                DocumentVersion.original_filename.label("original_filename"),
                DocumentVersion.file_type.label("file_type"),
                DocumentVersion.document_id.label("document_id"),
                Document.title.label("document_title"),
                Document.department_id.label("department_id"),
            )
            .join(DocumentVersion, DocumentVersion.id == Chunk.document_version_id)
            .join(Document, Document.id == DocumentVersion.document_id)
            .filter(Chunk.id.in_(chunk_ids))
            .all()
        )

        return {
            row.chunk_id: {
                "document_id": row.document_id,
                "document_version_id": row.document_version_id,
                "document_title": row.document_title,
                "original_filename": row.original_filename,
                "file_type": row.file_type,
                "version": row.version,
                "department_id": row.department_id,
            }
            for row in rows
        }

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
