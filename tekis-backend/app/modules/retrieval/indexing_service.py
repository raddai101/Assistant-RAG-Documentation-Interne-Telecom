"""
Service d'indexation vectorielle (Phase 2 — RAG baseline).

Découplé volontairement de `IngestionService` (Phase 1, close) : l'indexation est un
second pipeline explicite (`POST /api/v1/embeddings/reindex`), pas une modification
du chemin d'ingestion déjà testé. Cela respecte la règle de modification minimale
(§8) et l'isolation des frontières de module (§9, memoire.md §5).
"""
from dataclasses import dataclass

from app.modules.generation.contracts import EmbeddingClient
from app.modules.retrieval.contracts import VectorRecord, VectorStoreContract
from app.modules.retrieval.repository import RetrievalRepository


@dataclass
class IndexingResult:
    num_chunks_indexed: int


class EmbeddingIndexingService:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStoreContract,
        embedding_model_name: str,
        repository: RetrievalRepository | None = None,
    ):
        self._embedding_client = embedding_client
        self._vector_store = vector_store
        self._embedding_model_name = embedding_model_name
        self._repository = repository or RetrievalRepository()

    def index_pending_chunks(self, document_version_id: int | None = None) -> IndexingResult:
        chunks = self._repository.get_chunks_without_embedding(document_version_id)

        if not chunks:
            return IndexingResult(num_chunks_indexed=0)

        texts = [c.content for c in chunks]

        batch_embed = getattr(self._embedding_client, "embed_batch", None)
        vectors = (
            batch_embed(texts)
            if callable(batch_embed)
            else self._embedding_client.embed(texts)
        )

        if len(vectors) != len(chunks):
            raise ValueError(
                "Le client d'embedding a renvoyé un nombre de vecteurs différent du "
                "nombre de textes envoyés — indexation abandonnée pour éviter une "
                "association chunk/vecteur incorrecte."
            )

        # Cache des versions pour éviter de requêter PostgreSQL pour chaque chunk.
        versions = {}

        records = []

        for chunk, vector in zip(chunks, vectors):
            version = versions.get(chunk.document_version_id)

            if version is None:
                version = self._repository.get_document_version(
                    chunk.document_version_id
                )
                versions[chunk.document_version_id] = version

            chroma_id = f"chunk-{chunk.id}"

            records.append(
                VectorRecord(
                    id=chroma_id,
                    embedding=vector,
                    document=chunk.content,
                    metadata={
                        "chunk_id": chunk.id,
                        "document_version_id": chunk.document_version_id,
                        "page": chunk.page,
                        "section": chunk.section,
                        "original_filename": (
                            version.original_filename if version else None
                        ),
                        "document_title": (
                            version.document.title
                            if version and version.document
                            else None
                        ),
                    },
                )
            )

        try:
            self._vector_store.upsert(records)

            for chunk, vector, record in zip(chunks, vectors, records):
                self._repository.save_embedding_meta(
                    chunk=chunk,
                    embedding_model=self._embedding_model_name,
                    dimension=len(vector),
                    chroma_id=record.id,
                )

            self._repository.commit()

        except Exception:
            self._repository.rollback()
            raise

        return IndexingResult(num_chunks_indexed=len(chunks))