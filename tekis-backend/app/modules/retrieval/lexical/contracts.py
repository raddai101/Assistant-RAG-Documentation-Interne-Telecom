"""
Contrat de recherche lexicale (Phase 3 — Hybrid Retrieval, memoire.md §17 décision
#12 : PostgreSQL Full-Text Search confirmé). Isole le reste du système de
l'implémentation SQL concrète — même principe que `VectorStoreContract` (§3.1 :
« CHANGE IMPLEMENTATION, PRESERVE CONTRACT »).
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LexicalMatch:
    chunk_id: int
    content: str
    rank: float
    metadata: dict = field(default_factory=dict)


class LexicalSearchContract(Protocol):
    def search(
        self, query: str, top_k: int, document_version_ids: list[int] | None = None
    ) -> list[LexicalMatch]: ...
