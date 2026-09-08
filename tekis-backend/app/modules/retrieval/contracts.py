"""
Contrat du module `retrieval` (memoire.md §6.2, §9). Le module `retrieval` ne doit
jamais dépendre directement de ChromaDB : il passe exclusivement par
`VectorStoreContract`. C'est ce contrat qui a changé d'implémentation lors du pivot
Phase 0 session 2 (pgvector -> ChromaDB), pas son interface — principe « CHANGE
IMPLEMENTATION, PRESERVE CONTRACT ».
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class VectorRecord:
    """Un vecteur à indexer, avec sa métadonnée et le texte source (pour retour
    direct sans requête SQL supplémentaire lors du retrieval)."""

    id: str
    embedding: list[float]
    document: str
    metadata: dict = field(default_factory=dict)


@dataclass
class VectorSearchResult:
    id: str
    document: str
    metadata: dict
    distance: float | None = None


class VectorStoreContract(Protocol):
    def upsert(self, records: list[VectorRecord]) -> None: ...

    def search(
        self, query_embedding: list[float], top_k: int, where: dict | None = None
    ) -> list[VectorSearchResult]: ...

    def delete(self, ids: list[str]) -> None: ...

    def get(self, ids: list[str]) -> list[VectorRecord]: ...

    def health(self) -> bool: ...
