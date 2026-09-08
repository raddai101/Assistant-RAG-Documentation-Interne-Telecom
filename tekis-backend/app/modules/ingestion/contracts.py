"""
Contrat du module `ingestion`. Toute autre couche (API, autres modules) ne doit
dépendre que de ces interfaces, jamais des détails d'implémentation des parsers ou
du chunker — cela permet de changer une librairie de parsing sans casser le reste du
système (principe « CHANGE IMPLEMENTATION, PRESERVE CONTRACT », memoire.md §3.1).
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ParsedDocument:
    """Résultat neutre (indépendant du format source) produit par un parser."""

    text: str
    pages: list[str] = field(default_factory=list)  # texte par page, si applicable
    metadata: dict = field(default_factory=dict)


class DocumentParser(Protocol):
    """Contrat que chaque parser de format (PDF, DOCX, XLSX, TXT) doit respecter."""

    supported_extensions: tuple[str, ...]

    def parse(self, file_path: str) -> ParsedDocument: ...


@dataclass
class ChunkResult:
    content: str
    position: int
    section: str | None = None
    page: int | None = None


class Chunker(Protocol):
    def chunk(self, parsed: ParsedDocument) -> list[ChunkResult]: ...
