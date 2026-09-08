"""
Service du module `knowledge_graph` (Phase 4). Couche fine au-dessus du
`GraphStoreContract`, point d'entrée unique pour les routes API (§9).

**Hors périmètre de cette phase (volontairement)** : aucune extraction automatique
d'entités/relations depuis le texte des chunks (nécessiterait un pipeline NLP
dédié, non demandé explicitement — cf. §3 des instructions : ne pas développer une
fonctionnalité non demandée). Ce service expose l'infrastructure du graphe
(création/lecture d'entités et de relations, navigation), pas encore son
peuplement automatique.
"""
from app.modules.knowledge_graph.contracts import (
    GraphEntity,
    GraphRelationship,
    GraphStoreContract,
)


class EntityNotFoundError(ValueError):
    pass


class GraphService:
    def __init__(self, graph_store: GraphStoreContract):
        self._graph_store = graph_store

    def upsert_entity(self, entity: GraphEntity) -> GraphEntity:
        self._graph_store.upsert_entity(entity)
        return entity

    def upsert_relationship(self, relationship: GraphRelationship) -> GraphRelationship:
        # Garde-fou : pas de relation "orpheline" créée implicitement — les deux
        # entités doivent déjà exister. Cohérent avec la règle des instructions
        # permanentes : le graphe complète les documents, il ne doit pas devenir une
        # source de vérité incontrôlée qui invente sa propre ontologie au fil de l'eau.
        if self._graph_store.get_entity(relationship.source_id) is None:
            raise EntityNotFoundError(f"Entité source '{relationship.source_id}' introuvable.")
        if self._graph_store.get_entity(relationship.target_id) is None:
            raise EntityNotFoundError(f"Entité cible '{relationship.target_id}' introuvable.")

        self._graph_store.upsert_relationship(relationship)
        return relationship

    def get_entity(self, entity_id: str) -> GraphEntity | None:
        return self._graph_store.get_entity(entity_id)

    def get_related_entities(
        self, entity_id: str, relationship_type: str | None = None, depth: int = 1
    ) -> list[GraphEntity]:
        return self._graph_store.get_related_entities(entity_id, relationship_type, depth)

    def delete_entity(self, entity_id: str) -> None:
        self._graph_store.delete_entity(entity_id)

    def find_entities_by_source_chunk_ids(self, chunk_ids: list[int]):
        return self._graph_store.find_entities_by_source_chunk_ids(chunk_ids)

    def get_related_facts(self, entity_id: str, depth: int = 5) -> list[str]:
        getter = getattr(self._graph_store, "get_related_facts", None)
        return getter(entity_id, depth=depth) if getter else []

    def find_entities_by_query(self, query: str):
        finder = getattr(self._graph_store, "find_entities_by_query", None)
        return finder(query) if finder else []
