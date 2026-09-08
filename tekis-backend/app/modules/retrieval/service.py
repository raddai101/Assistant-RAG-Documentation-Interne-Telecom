"""
Service de retrieval Phase 2 (baseline) : recherche vectorielle simple, sans fusion
lexicale ni reranking (Hybrid Retrieval = Phase 3, memoire.md §9). Utilisé pour
`POST /api/v1/search` (retrieval brut, sans génération — utile pour debug/éval,
memoire.md §7) et par `GenerationService` (module `generation`) pour construire le
contexte du LLM.
"""
from dataclasses import dataclass

from app.modules.generation.contracts import EmbeddingClient
from app.modules.retrieval.contracts import VectorSearchResult, VectorStoreContract


@dataclass
class RetrievalResult:
    results: list[VectorSearchResult]


class RetrievalService:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStoreContract,
        default_top_k: int = 10,
    ):
        self._embedding_client = embedding_client
        self._vector_store = vector_store
        self._default_top_k = default_top_k

    def search(
        self,
        query: str,
        top_k: int | None = None,
        authorized_document_version_ids: set[int] | None = None,
    ) -> RetrievalResult:
        # `authorized_document_version_ids` (Phase 5) : None = pas de restriction
        # (compat. Phase 2/3 sans auth) ; ensemble vide = accès refusé à tout, on ne
        # va même pas jusqu'au vector store (§15 : pas de doc interdit récupéré).
        if authorized_document_version_ids is not None and not authorized_document_version_ids:
            return RetrievalResult(results=[])

        where = (
            {"document_version_id": {"$in": list(authorized_document_version_ids)}}
            if authorized_document_version_ids is not None
            else None
        )

        query_embedding = self._embedding_client.embed([query])[0]
        results = self._vector_store.search(
            query_embedding, top_k=top_k or self._default_top_k, where=where
        )
        return RetrievalResult(results=results)
