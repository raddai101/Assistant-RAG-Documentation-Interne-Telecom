"""
Repository du module `ingestion`.

Seul point d'accès à PostgreSQL pour la persistance des documents/versions/chunks
(§9 des instructions : « les accès aux bases de données doivent être isolés »).
Le `service.py` ne manipule jamais `db.session` directement — il passe par ici.
"""
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.chunk import Chunk
from app.modules.ingestion.contracts import ChunkResult


class IngestionRepository:
    def get_or_create_document(
        self,
        title: str,
        department_id: int | None = None,
        classification: str | None = None,
        owner_id: int | None = None,
        document_id: int | None = None,
    ) -> Document:
        """
        Si `document_id` est fourni, on ingère une nouvelle version d'un document
        existant. Sinon, un nouveau `Document` est créé (première ingestion).
        """
        if document_id is not None:
            document = db.session.get(Document, document_id)
            if document is None:
                raise ValueError(f"Document id={document_id} introuvable.")
            return document

        document = Document(
            title=title,
            department_id=department_id,
            classification=classification,
            owner_id=owner_id,
        )
        db.session.add(document)
        db.session.flush()  # obtient document.id sans committer
        return document

    def next_version_number(self, document: Document) -> int:
        existing = [v.version for v in document.versions]
        return max(existing, default=0) + 1

    def create_version(
        self,
        document: Document,
        storage_path: str,
        checksum: str,
        original_filename: str,
        file_type: str,
        supersedes_version_id: int | None = None,
        status: DocumentStatus = DocumentStatus.ACTIVE,
    ) -> DocumentVersion:
        version_number = self.next_version_number(document)

        # Si cette version en remplace une autre, l'ancienne passe au statut
        # SUPERSEDED — la résolution temporelle fine (valid_from/valid_to) reste
        # non implémentée avant la Phase 5, mais le statut est déjà cohérent.
        if supersedes_version_id is not None:
            previous = db.session.get(DocumentVersion, supersedes_version_id)
            if previous is not None:
                previous.status = DocumentStatus.SUPERSEDED

        version = DocumentVersion(
            document_id=document.id,
            version=version_number,
            status=status,
            supersedes_version_id=supersedes_version_id,
            storage_path=storage_path,
            checksum=checksum,
            original_filename=original_filename,
            file_type=file_type,
        )
        db.session.add(version)
        db.session.flush()
        return version

    def save_chunks(
        self, document_version: DocumentVersion, chunk_results: list[ChunkResult], chunk_hashes: list[str]
    ) -> list[Chunk]:
        chunks = []
        for result, content_hash in zip(chunk_results, chunk_hashes):
            chunk = Chunk(
                document_version_id=document_version.id,
                section=result.section,
                page=result.page,
                content=result.content,
                position=result.position,
                content_hash=content_hash,
            )
            db.session.add(chunk)
            chunks.append(chunk)
        db.session.flush()
        return chunks

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
