"""
Contrats du module `change_intelligence` (Phase 7, memoire.md §15) : alignement
V(n-1)/V(n), détection ajouts/suppressions/modifications, analyse d'impact.

Implémentée en dernier, conformément à la règle explicite du projet (« Le Change
Intelligent doit être implémenter à la fin de toute les fonctionnalités » —
instructions permanentes §26).
"""
from dataclasses import dataclass, field
from enum import Enum


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class ChunkDiff:
    change_type: ChangeType
    chunk_id_from: int | None  # None si ADDED
    chunk_id_to: int | None  # None si REMOVED
    content_from: str | None
    content_to: str | None
    similarity: float | None = None  # pertinent seulement pour MODIFIED


@dataclass
class VersionComparisonResult:
    document_id: int
    version_from: int
    version_to: int
    diffs: list[ChunkDiff] = field(default_factory=list)

    @property
    def additions(self) -> list[ChunkDiff]:
        return [d for d in self.diffs if d.change_type == ChangeType.ADDED]

    @property
    def removals(self) -> list[ChunkDiff]:
        return [d for d in self.diffs if d.change_type == ChangeType.REMOVED]

    @property
    def modifications(self) -> list[ChunkDiff]:
        return [d for d in self.diffs if d.change_type == ChangeType.MODIFIED]

    @property
    def unchanged_count(self) -> int:
        return len([d for d in self.diffs if d.change_type == ChangeType.UNCHANGED])


@dataclass
class ImpactedEntity:
    entity_id: str
    type: str
    name: str
    via_chunk_ids: list[int] = field(default_factory=list)  # traçabilité (§18)


@dataclass
class ImpactAnalysisResult:
    directly_linked_entities: list[ImpactedEntity] = field(default_factory=list)
    indirectly_related_entities: list[ImpactedEntity] = field(default_factory=list)
