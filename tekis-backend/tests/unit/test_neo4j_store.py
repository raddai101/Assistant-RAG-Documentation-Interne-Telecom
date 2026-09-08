"""
Aucun serveur Neo4j n'est disponible dans cet environnement de développement
(memoire.md §26) : ces tests injectent un driver Neo4j entièrement factice pour
vérifier la construction des requêtes Cypher et le mapping résultat -> `GraphEntity`,
indépendamment d'un vrai serveur.
"""
import pytest

from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore


class FakeNode(dict):
    pass


class FakeRecord(dict):
    pass


class FakeResult:
    def __init__(self, records):
        self._records = records

    def single(self):
        return self._records[0] if self._records else None

    def __iter__(self):
        return iter(self._records)


class FakeSession:
    def __init__(self, driver):
        self._driver = driver

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def run(self, cypher, **params):
        self._driver.queries.append((cypher, params))
        return self._driver.next_result


class FakeDriver:
    def __init__(self):
        self.queries = []
        self.next_result = FakeResult([])

    def session(self):
        return FakeSession(self)

    def close(self):
        pass


@pytest.fixture
def fake_driver():
    return FakeDriver()


@pytest.fixture
def store(fake_driver):
    return Neo4jGraphStore(driver=fake_driver)


def test_upsert_entity_sends_merge_query_with_correct_params(store, fake_driver):
    entity = GraphEntity(id="bts:1", type="BTS", name="BTS Kinshasa 1", properties={"puissance": 40}, source_chunk_ids=[7])

    store.upsert_entity(entity)

    cypher, params = fake_driver.queries[-1]
    assert "MERGE (e:Entity" in cypher
    assert params["id"] == "bts:1"
    assert params["type"] == "BTS"
    assert params["source_chunk_ids"] == [7]


def test_get_entity_returns_none_when_not_found(store, fake_driver):
    fake_driver.next_result = FakeResult([])

    result = store.get_entity("inconnu")

    assert result is None


def test_get_entity_maps_node_to_graph_entity(store, fake_driver):
    node = FakeNode(id="bsc:1", type="BSC", name="BSC Centre", properties={"zone": "Nord"}, source_chunk_ids=[3, 4])
    fake_driver.next_result = FakeResult([FakeRecord(e=node)])

    result = store.get_entity("bsc:1")

    assert result == GraphEntity(id="bsc:1", type="BSC", name="BSC Centre", properties={"zone": "Nord"}, source_chunk_ids=[3, 4])


def test_upsert_relationship_requires_valid_type_token(store):
    bad_relationship = GraphRelationship(source_id="bts:1", target_id="bsc:1", type="LIEN INVALIDE; DROP")

    with pytest.raises(ValueError, match="injection Cypher"):
        store.upsert_relationship(bad_relationship)


def test_upsert_relationship_sends_merge_query_with_interpolated_type(store, fake_driver):
    relationship = GraphRelationship(source_id="bts:1", target_id="bsc:1", type="CONNECTED_TO", source_chunk_ids=[9])

    store.upsert_relationship(relationship)

    cypher, params = fake_driver.queries[-1]
    assert "MERGE (a)-[r:CONNECTED_TO]->(b)" in cypher
    assert params["source_id"] == "bts:1"
    assert params["target_id"] == "bsc:1"
    assert params["source_chunk_ids"] == [9]


def test_get_related_entities_clamps_depth_to_max_five(store, fake_driver):
    fake_driver.next_result = FakeResult([])

    store.get_related_entities("bts:1", depth=99)

    cypher, _ = fake_driver.queries[-1]
    assert "*1..5" in cypher


def test_get_related_entities_filters_by_relationship_type(store, fake_driver):
    fake_driver.next_result = FakeResult([])

    store.get_related_entities("bts:1", relationship_type="CONNECTED_TO", depth=2)

    cypher, _ = fake_driver.queries[-1]
    assert ":CONNECTED_TO" in cypher
    assert "*1..2" in cypher


def test_get_related_entities_rejects_invalid_type_token(store):
    with pytest.raises(ValueError, match="injection Cypher"):
        store.get_related_entities("bts:1", relationship_type="BAD TYPE")


def test_delete_entity_sends_detach_delete(store, fake_driver):
    store.delete_entity("bts:1")

    cypher, params = fake_driver.queries[-1]
    assert "DETACH DELETE" in cypher
    assert params["id"] == "bts:1"
