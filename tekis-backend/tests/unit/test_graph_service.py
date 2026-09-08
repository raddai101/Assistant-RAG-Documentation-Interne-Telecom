import pytest

from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship
from app.modules.knowledge_graph.service import GraphService, EntityNotFoundError


class InMemoryGraphStore:
    """Double de test complet du GraphStoreContract, sans dépendance à Neo4j."""

    def __init__(self):
        self._entities: dict[str, GraphEntity] = {}
        self._relationships: list[GraphRelationship] = []

    def upsert_entity(self, entity):
        self._entities[entity.id] = entity

    def upsert_relationship(self, relationship):
        self._relationships.append(relationship)

    def get_entity(self, entity_id):
        return self._entities.get(entity_id)

    def get_related_entities(self, entity_id, relationship_type=None, depth=1):
        related_ids = set()
        for rel in self._relationships:
            if relationship_type and rel.type != relationship_type:
                continue
            if rel.source_id == entity_id:
                related_ids.add(rel.target_id)
            elif rel.target_id == entity_id:
                related_ids.add(rel.source_id)
        return [self._entities[rid] for rid in related_ids if rid in self._entities]

    def delete_entity(self, entity_id):
        self._entities.pop(entity_id, None)


@pytest.fixture
def service():
    return GraphService(InMemoryGraphStore())


def test_upsert_entity_stores_and_returns_it(service):
    entity = GraphEntity(id="bts:1", type="BTS", name="BTS Kinshasa 1")

    result = service.upsert_entity(entity)

    assert result == entity
    assert service.get_entity("bts:1") == entity


def test_upsert_relationship_requires_source_entity_to_exist(service):
    service.upsert_entity(GraphEntity(id="bsc:1", type="BSC", name="BSC Centre"))
    relationship = GraphRelationship(source_id="bts:inconnu", target_id="bsc:1", type="CONNECTED_TO")

    with pytest.raises(EntityNotFoundError, match="bts:inconnu"):
        service.upsert_relationship(relationship)


def test_upsert_relationship_requires_target_entity_to_exist(service):
    service.upsert_entity(GraphEntity(id="bts:1", type="BTS", name="BTS 1"))
    relationship = GraphRelationship(source_id="bts:1", target_id="bsc:inconnu", type="CONNECTED_TO")

    with pytest.raises(EntityNotFoundError, match="bsc:inconnu"):
        service.upsert_relationship(relationship)


def test_upsert_relationship_succeeds_when_both_entities_exist(service):
    service.upsert_entity(GraphEntity(id="bts:1", type="BTS", name="BTS 1"))
    service.upsert_entity(GraphEntity(id="bsc:1", type="BSC", name="BSC 1"))
    relationship = GraphRelationship(source_id="bts:1", target_id="bsc:1", type="CONNECTED_TO", source_chunk_ids=[5])

    result = service.upsert_relationship(relationship)

    assert result == relationship


def test_get_related_entities_returns_connected_entities(service):
    service.upsert_entity(GraphEntity(id="bts:1", type="BTS", name="BTS 1"))
    service.upsert_entity(GraphEntity(id="bsc:1", type="BSC", name="BSC 1"))
    service.upsert_relationship(GraphRelationship(source_id="bts:1", target_id="bsc:1", type="CONNECTED_TO"))

    related = service.get_related_entities("bts:1")

    assert len(related) == 1
    assert related[0].id == "bsc:1"


def test_get_entity_returns_none_when_absent(service):
    assert service.get_entity("inconnu") is None


def test_delete_entity_removes_it(service):
    service.upsert_entity(GraphEntity(id="bts:1", type="BTS", name="BTS 1"))

    service.delete_entity("bts:1")

    assert service.get_entity("bts:1") is None
