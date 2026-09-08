"""
Repository du module `governance` (Phase 5). Isolé des autres repositories (§9) —
lit `Permission` et `DocumentVersion`, ne les modifie jamais depuis ce module.
"""
from app.extensions import db
from app.models.document import Document, DocumentVersion, Permission


class GovernanceRepository:
    def get_all_document_versions(self) -> list[DocumentVersion]:
        return db.session.query(DocumentVersion).all()

    def get_permissions_for_document(
        self, document_id: int, document_version_id: int
    ) -> list[Permission]:
        """Permissions applicables à une version : celles définies au niveau du
        document (portée à toutes ses versions) OU spécifiquement à cette version."""
        return (
            db.session.query(Permission)
            .filter(
                (Permission.document_id == document_id)
                | (Permission.document_version_id == document_version_id)
            )
            .all()
        )

    def get_document(self, document_id: int) -> Document | None:
        return db.session.get(Document, document_id)
