"""
Repository du module `validation` (Phase 6). Isolé des autres repositories (§9) —
lecture seule sur `DocumentVersion`.
"""
from app.extensions import db
from app.models.document import DocumentVersion


class ValidationRepository:
    def get_document_versions(self, version_ids: list[int]) -> list[DocumentVersion]:
        if not version_ids:
            return []
        return (
            db.session.query(DocumentVersion)
            .filter(DocumentVersion.id.in_(version_ids))
            .all()
        )
