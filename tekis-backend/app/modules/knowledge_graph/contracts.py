"""
Contrats du module `knowledge_graph` (Phase 4, memoire.md §10, §17 décision #13 :
Neo4j confirmé disponible en infrastructure). Isole le reste du système du moteur de
graphe concret — même principe que `VectorStoreContract`/`LexicalSearchContract`
(§3.1 : « CHANGE IMPLEMENTATION, PRESERVE CONTRACT »).

Rappel des instructions permanentes du projet (règle §18, non renumérotée ici) : le
Knowledge Graph COMPLÈTE les documents, il ne devient jamais automatiquement la
source unique de vérité, et toute relation doit rester traçable vers ses sources
documentaires quand c'est pertinent — d'où le champ `source_chunk_ids` obligatoire
(même vide) sur `GraphEntity` et `GraphRelationship`.
"""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class GraphEntity:
    id: str  # identifiant stable et lisible, ex. "bts:kinshasa-01"
    type: str  # ex. "BTS", "BSC", "CoreNetwork", "Department", "Document"
    name: str
    properties: dict = field(default_factory=dict)
    source_chunk_ids: list[int] = field(default_factory=list)  # traçabilité (§18)


@dataclass
class GraphRelationship:
    source_id: str
    target_id: str
    type: str  # ex. "CONNECTED_TO", "MANAGED_BY", "DEPENDS_ON"
    properties: dict = field(default_factory=dict)
    source_chunk_ids: list[int] = field(default_factory=list)


class GraphStoreContract(Protocol):
    def upsert_entity(self, entity: GraphEntity) -> None: ...

    def upsert_relationship(self, relationship: GraphRelationship) -> None: ...

    def get_entity(self, entity_id: str) -> GraphEntity | None: ...

    def get_related_entities(
        self, entity_id: str, relationship_type: str | None = None, depth: int = 1
    ) -> list[GraphEntity]: ...

    def delete_entity(self, entity_id: str) -> None: ...

    def find_entities_by_source_chunk_ids(self, chunk_ids: list[int]) -> list[GraphEntity]:
        """Entités directement tracées (`source_chunk_ids`) vers l'un des chunks
        donnés — point d'entrée de l'analyse d'impact Phase 7 (memoire.md §15) : à
        partir des chunks modifiés d'un document, retrouver les entités du graphe
        directement concernées avant de naviguer vers leurs entités liées."""
        ...
