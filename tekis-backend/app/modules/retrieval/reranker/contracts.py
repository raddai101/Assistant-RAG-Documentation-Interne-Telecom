"""
Contrat du reranker (Phase 3, memoire.md §17 décision #11 : cross-encoder
`BAAI/bge-reranker-v2-m3`).
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class RerankCandidate:
    chunk_id: int
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class RerankedResult:
    chunk_id: int
    content: str
    metadata: dict
    score: float  # score du cross-encoder — plus haut = plus pertinent


class RerankerContract(Protocol):
    def rerank(
        self, query: str, candidates: list[RerankCandidate], top_k: int
    ) -> list[RerankedResult]: ...
