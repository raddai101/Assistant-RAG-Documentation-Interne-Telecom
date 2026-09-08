"""
Service du module `ingestion`.

Statut Phase 1 (complète) : orchestration quarantaine -> validation -> parse -> chunk
-> persistance. `process_file()` reste une fonction pure (aucune écriture) — elle
sert aux tests unitaires et à un futur usage "aperçu avant ingestion". `ingest()`
attend un fichier déjà en quarantaine (voir `app/api/ingestion`, qui utilise
`QuarantineManager.stage()` avant d'appeler ce service) : c'est la route HTTP qui
place le fichier en quarantaine, le service ne fait que le valider et le libérer.
"""
import hashlib
from dataclasses import dataclass

from app.modules.ingestion.contracts import ChunkResult
from app.modules.ingestion.parsers import get_parser_for
from app.modules.ingestion.chunking.chunker import FixedSizeChunker
from app.modules.ingestion.repository import IngestionRepository
from app.modules.ingestion.validation import FileValidator, FileValidationError
from app.modules.ingestion.quarantine import QuarantineManager


@dataclass
class IngestionResult:
    document_id: int
    document_version_id: int
    version_number: int
    num_chunks: int
    checksum: str


class IngestionService:
    def __init__(
        self,
        chunker: FixedSizeChunker | None = None,
        repository: IngestionRepository | None = None,
        validator: FileValidator | None = None,
        quarantine_manager: QuarantineManager | None = None,
        storage_dir: str = "./data/documents",
        quarantine_dir: str = "./data/quarantine",
        max_upload_size_mb: int = 50,
    ):
        self._chunker = chunker or FixedSizeChunker()
        self._repository = repository or IngestionRepository()
        self._validator = validator or FileValidator(max_size_mb=max_upload_size_mb)
        self._quarantine = quarantine_manager or QuarantineManager(quarantine_dir)
        self._storage_dir = storage_dir

    def process_file(self, file_path: str) -> list[ChunkResult]:
        """
        Parse un fichier puis le découpe en chunks. Ne touche pas la base.
        Le parser est choisi selon l'extension de `file_path` lui-même — à utiliser
        uniquement quand ce chemin porte la bonne extension (ex. tests unitaires).
        """
        parser = get_parser_for(file_path)
        parsed = parser.parse(file_path)
        return self._chunker.chunk(parsed)

    def _parse_and_chunk(self, file_path: str, original_filename: str) -> list[ChunkResult]:
        """Choisit le parser selon `original_filename`, mais lit le contenu depuis
        `file_path` (utile quand le fichier stocké temporairement n'a pas d'extension,
        ex. upload HTTP)."""
        parser = get_parser_for(original_filename)
        parsed = parser.parse(file_path)
        return self._chunker.chunk(parsed)

    def ingest(
        self,
        quarantine_file_path: str,
        original_filename: str,
        title: str,
        department_id: int | None = None,
        classification: str | None = None,
        owner_id: int | None = None,
        document_id: int | None = None,
        supersedes_version_id: int | None = None,
    ) -> IngestionResult:
        """
        Pipeline complet Phase 1 : validation (taille réelle, extension, signature de
        contenu) -> parse -> chunk -> libération du fichier vers le stockage définitif
        -> persistance (Document, DocumentVersion, Chunks).

        `quarantine_file_path` DOIT pointer vers un fichier déjà en quarantaine
        (jamais un chemin arbitraire) : en cas de rejet, ce fichier est déplacé vers
        `quarantine/rejected/` avec le motif tracé, jamais supprimé silencieusement.
        """
        try:
            self._validator.validate(quarantine_file_path, original_filename)
        except FileValidationError as e:
            self._quarantine.reject(quarantine_file_path, reason=str(e))
            raise

        try:
            chunk_results = self._parse_and_chunk(quarantine_file_path, original_filename)
            checksum = self.compute_checksum(quarantine_file_path)
        except Exception as e:
            # Le fichier a passé la validation de signature mais le parsing échoue
            # quand même (ex. PDF tronqué au-delà de l'en-tête) : rejeté et tracé
            # comme un fichier non conforme (400), jamais une erreur serveur (500) —
            # et jamais laissé en quarantaine sans explication.
            reason = f"Échec du parsing malgré une signature valide : {e}"
            self._quarantine.reject(quarantine_file_path, reason=reason)
            raise FileValidationError(
                "Le fichier a une extension et une signature valides mais son "
                "contenu est illisible ou corrompu."
            ) from e

        # Le fichier a passé toutes les validations : il quitte la quarantaine pour
        # le stockage définitif.
        stored_path = self._quarantine.release(quarantine_file_path, self._storage_dir)

        ext = original_filename[original_filename.rfind(".") :].lower()
        try:
            document = self._repository.get_or_create_document(
                title=title,
                department_id=department_id,
                classification=classification,
                owner_id=owner_id,
                document_id=document_id,
            )
            version = self._repository.create_version(
                document=document,
                storage_path=stored_path,
                checksum=checksum,
                original_filename=original_filename,
                file_type=ext.lstrip("."),
                supersedes_version_id=supersedes_version_id,
            )
            chunk_hashes = [self.compute_chunk_hash(c.content) for c in chunk_results]
            self._repository.save_chunks(version, chunk_results, chunk_hashes)
            self._repository.commit()
        except Exception:
            self._repository.rollback()
            raise

        return IngestionResult(
            document_id=document.id,
            document_version_id=version.id,
            version_number=version.version,
            num_chunks=len(chunk_results),
            checksum=checksum,
        )

    @staticmethod
    def compute_checksum(file_path: str) -> str:
        """SHA-256 du fichier source, utilisé pour `document_versions.checksum`."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha256.update(block)
        return sha256.hexdigest()

    @staticmethod
    def compute_chunk_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


