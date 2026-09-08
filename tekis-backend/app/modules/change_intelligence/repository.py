"""
Repository du module `change_intelligence` (§9 : accès DB isolés). Convertit les
modèles SQLAlchemy en objets neutres (`ChunkForDiff`) attendus par `diff_service.py`.
"""
from app.extensions import db
from app.models.document import Document, DocumentVersion
from app.models.chunk import Chunk
from app.modules.change_intelligence.diff_service import ChunkForDiff


class DocumentVersionNotFoundError(ValueError):
    pass


class ChangeIntelligenceRepository:
    def get_document(self, document_id: int) -> Document | None:
        return db.session.get(Document, document_id)

    def get_version(self, document_id: int, version_number: int) -> DocumentVersion | None:
        return (
            DocumentVersion.query.filter_by(document_id=document_id, version=version_number)
            .first()
        )

    def get_latest_two_versions(self, document_id: int) -> tuple[DocumentVersion, DocumentVersion] | None:
        """Renvoie (version précédente, version la plus récente) triées par numéro de
        version, ou None si le document a moins de deux versions."""
        versions = (
            DocumentVersion.query.filter_by(document_id=document_id)
            .order_by(DocumentVersion.version.desc())
            .limit(2)
            .all()
        )
        if len(versions) < 2:
            return None
        version_to, version_from = versions[0], versions[1]
        return version_from, version_to

    def get_chunks_for_version(self, document_version_id: int) -> list[ChunkForDiff]:
        chunks = Chunk.query.filter_by(document_version_id=document_version_id).all()
        return [ChunkForDiff(chunk_id=c.id, content=c.content, content_hash=c.content_hash) for c in chunks]
