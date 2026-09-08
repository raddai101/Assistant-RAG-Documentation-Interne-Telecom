"""
Implémentation ChromaDB du contrat `VectorStoreContract` (validé memoire.md §4).
Utilise un client persistant local (pas de serveur ChromaDB distant en Phase 2).
"""
import chromadb

from app.modules.retrieval.contracts import VectorRecord, VectorMatch


class ChromaVectorStore:
    def __init__(self, persist_dir: str, collection_name: str):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def upsert(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        self._collection.upsert(
            ids=[r.id for r in records],
            embeddings=[r.embedding for r in records],
            documents=[r.document for r in records],
            metadatas=[r.metadata for r in records],
        )

    def query(self, embedding: list[float], top_k: int = 5) -> list[VectorMatch]:
        results = self._collection.query(query_embeddings=[embedding], n_results=top_k)

        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            VectorMatch(id=ids[i], document=documents[i], metadata=metadatas[i], distance=distances[i])
            for i in range(len(ids))
        ]
