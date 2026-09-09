"""
Service de retrieval hybride (Phase 3, memoire.md §9) : fusion lexicale (PostgreSQL
FTS) + vectorielle (ChromaDB, Phase 2), puis reranking par cross-encoder.

Expose volontairement la MÊME interface publique que `RetrievalService` (Phase 2) —
`.search(query, top_k) -> RetrievalResult` avec des `VectorSearchResult` — pour que
`GenerationService` (module `generation`) n'ait **aucune modification à subir**
(§3.1 : « CHANGE IMPLEMENTATION, PRESERVE CONTRACT »). Seule la fabrique de service
utilisée par les routes `search`/`chat` change (Phase 2 -> Phase 3).

Note de sémantique (à ne pas découvrir silencieusement) : le champ `distance` de
`VectorSearchResult` porte ici le **score du reranker** (plus haut = plus pertinent),
et non plus une distance vectorielle brute comme en Phase 2 (où plus bas = plus
proche). Ce changement de sens est délibéré et documenté ici plutôt que laissé
implicite — voir memoire.md §24.
"""
from app.modules.generation.contracts import EmbeddingClient
from app.modules.retrieval.contracts import VectorSearchResult, VectorStoreContract
from app.modules.retrieval.service import RetrievalResult
from app.modules.retrieval.repository import RetrievalRepository
from app.modules.retrieval.lexical.contracts import LexicalSearchContract
from app.modules.retrieval.reranker.contracts import RerankCandidate, RerankerContract
import logging
import time

logger = logging.getLogger(__name__)
from app.modules.retrieval.fusion import reciprocal_rank_fusion


class HybridRetrievalService:
    def __init__(
        self,
        embedding_client: EmbeddingClient,
        vector_store: VectorStoreContract,
        lexical_search: LexicalSearchContract,
        reranker: RerankerContract,
        default_top_k: int = 10,
        candidate_k: int = 20,
    ):
        self._embedding_client = embedding_client
        self._vector_store = vector_store
        self._lexical_search = lexical_search
        self._reranker = reranker
        self._repository = RetrievalRepository()
        self._default_top_k = default_top_k
        self._candidate_k = candidate_k

    def search(
        self,
        query: str,
        top_k: int | None = None,
        authorized_document_version_ids: set[int] | None = None,
    ) -> RetrievalResult:
        # Même politique que `RetrievalService` (Phase 2/5) : ensemble vide = deny
        # total sans interroger ni le vectoriel ni le lexical.
        if authorized_document_version_ids is not None and not authorized_document_version_ids:
            return RetrievalResult(results=[])

        final_top_k = top_k or self._default_top_k
        where = (
            {"document_version_id": {"$in": list(authorized_document_version_ids)}}
            if authorized_document_version_ids is not None
            else None
        )
        version_ids_list = (
            list(authorized_document_version_ids)
            if authorized_document_version_ids is not None
            else None
        )

        started = time.perf_counter()
        query_embedding = self._embedding_client.embed([query])[0]
        logger.info("[PERF] embedding query: %.3fs", time.perf_counter() - started)

        started = time.perf_counter()
        vector_matches = self._vector_store.search(
            query_embedding, top_k=self._candidate_k, where=where
        )
        logger.info("[PERF] recherche vectorielle: %.3fs (%d résultats)", time.perf_counter() - started, len(vector_matches))

        started = time.perf_counter()
        lexical_matches = self._lexical_search.search(
            query, top_k=self._candidate_k, document_version_ids=version_ids_list
        )
        logger.info("[PERF] recherche lexicale: %.3fs (%d résultats)", time.perf_counter() - started, len(lexical_matches))

        vector_ranked = [
            (match.metadata.get("chunk_id"), match.document, match.metadata)
            for match in vector_matches
            if match.metadata.get("chunk_id") is not None
        ]
        lexical_ranked = [(m.chunk_id, m.content, m.metadata) for m in lexical_matches]

        fused = reciprocal_rank_fusion(vector_ranked, lexical_ranked)
        if not fused:
            return RetrievalResult(results=[])

        candidates = [
            RerankCandidate(chunk_id=f.chunk_id, content=f.content, metadata=f.metadata)
            for f in fused[: self._candidate_k]
        ]
        started = time.perf_counter()
        reranked = self._reranker.rerank(query, candidates, top_k=final_top_k)
        logger.info("[PERF] reranker: %.3fs (%d candidats -> %d résultats)", time.perf_counter() - started, len(candidates), len(reranked))

        source_metadata = self._repository.get_source_metadata([r.chunk_id for r in reranked])
        results = []
        for r in reranked:
            metadata = {**r.metadata, "chunk_id": r.chunk_id}
            metadata.update(source_metadata.get(r.chunk_id, {}))
            results.append(
                VectorSearchResult(
                    id=f"chunk-{r.chunk_id}",
                    document=r.content,
                    metadata=metadata,
                    distance=r.score,
                )
            )
        return RetrievalResult(results=results)
