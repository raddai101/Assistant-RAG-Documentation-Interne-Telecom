"""
Contrats du module `generation`. Toute autre couche ne dépend que de ces interfaces,
jamais du détail d'exécution (Ollama aujourd'hui, potentiellement autre chose plus
tard) — même principe « CHANGE IMPLEMENTATION, PRESERVE CONTRACT » que pour le
`VectorStoreContract` (memoire.md §3.1, §6.2).
"""
from typing import Iterator, Protocol


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str: ...
    def stream(self, prompt: str) -> Iterator[str]: ...
