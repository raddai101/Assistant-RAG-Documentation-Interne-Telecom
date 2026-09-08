"""
Implémentation ChromaDB du `VectorStoreContract` (memoire.md §6.2, décision #7).
Seul fichier du projet qui importe `chromadb` directement — le reste du système
(retrieval, generation, API) ne connaît que le contrat.
"""
import chromadb

from app.modules.retrieval.contracts import VectorRecord, VectorSearchResult


class ChromaVectorStore:
    def __init__(self, persist_dir: str, collection_name: str):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        # ChromaDB rejette un dict de métadonnées vide (`{}`) — un chunk sans page ni
        # section (ex. DOCX/TXT) produit ce cas légitimement. On convertit donc tout
        # dict vide en `None`, que ChromaDB accepte explicitement.
        self._collection.upsert(
            ids=[r.id for r in records],
            embeddings=[r.embedding for r in records],
            documents=[r.document for r in records],
            metadatas=[r.metadata or None for r in records],
        )

    def search(
        self, query_embedding: list[float], top_k: int = 5, where: dict | None = None
    ) -> list[VectorSearchResult]:
        # `where` (Phase 5) : filtre par métadonnées ChromaDB natif (ex.
        # {"document_version_id": {"$in": [1, 3, 7]}}) — utilisé pour restreindre le
        # retrieval aux versions autorisées (ACL) et temporellement valides AVANT
        # que le LLM ne voie quoi que ce soit (§15 des instructions).
        results = self._collection.query(
            query_embeddings=[query_embedding], n_results=top_k, where=where
        )
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0] if results.get("distances") else [None] * len(ids)

        return [
            VectorSearchResult(id=i, document=d, metadata=m or {}, distance=dist)
            for i, d, m, dist in zip(ids, documents, metadatas, distances)
        ]

    def delete(self, ids: list[str]) -> None:
        if not ids:
            return
        self._collection.delete(ids=ids)

    def get(self, ids: list[str]) -> list[VectorRecord]:
        if not ids:
            return []
        results = self._collection.get(ids=ids, include=["embeddings", "documents", "metadatas"])
        out = []
        for i, emb, doc, meta in zip(
            results.get("ids", []),
            results.get("embeddings", []),
            results.get("documents", []),
            results.get("metadatas", []),
        ):
            out.append(VectorRecord(id=i, embedding=list(emb), document=doc, metadata=meta or {}))
        return out

    def health(self) -> bool:
        try:
            self._client.heartbeat()
            return True
        except Exception:
            return False
