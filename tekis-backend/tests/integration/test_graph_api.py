"""
Aucun serveur Neo4j n'est disponible dans ce sandbox (memoire.md §26) :
`Neo4jGraphStore` est monkeypatché à l'endroit où le blueprint l'importe, remplacé
par un store en mémoire, pour vérifier le câblage HTTP -> service -> réponse JSON.
La vérification avec un Neo4j réel reste à faire par Radda101 sur son
infrastructure.
"""
import pytest

from app import create_app
from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship


class InMemoryGraphStore:
    def __init__(self, uri=None, user=None, password=None):
        pass

    _entities: dict = {}
    _relationships: list = []

    def __new__(cls, *args, **kwargs):
        # Un seul état partagé entre toutes les instances créées pendant un test
        # (chaque route reconstruit un `GraphService` -> un nouveau store), pour
        # simuler la persistance d'un vrai serveur Neo4j entre deux requêtes HTTP.
        instance = super().__new__(cls)
        return instance

    def upsert_entity(self, entity):
        InMemoryGraphStore._entities[entity.id] = entity

    def upsert_relationship(self, relationship):
        InMemoryGraphStore._relationships.append(relationship)

    def get_entity(self, entity_id):
        return InMemoryGraphStore._entities.get(entity_id)

    def get_related_entities(self, entity_id, relationship_type=None, depth=1):
        related_ids = set()
        for rel in InMemoryGraphStore._relationships:
            if relationship_type and rel.type != relationship_type:
                continue
            if rel.source_id == entity_id:
                related_ids.add(rel.target_id)
            elif rel.target_id == entity_id:
                related_ids.add(rel.source_id)
        return [InMemoryGraphStore._entities[rid] for rid in related_ids if rid in InMemoryGraphStore._entities]

    def delete_entity(self, entity_id):
        InMemoryGraphStore._entities.pop(entity_id, None)


@pytest.fixture(autouse=True)
def reset_store():
    InMemoryGraphStore._entities = {}
    InMemoryGraphStore._relationships = []
    yield


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr("app.api.graph.Neo4jGraphStore", InMemoryGraphStore)
    return create_app("testing")


@pytest.fixture
def client(app):
    return app.test_client()


def test_create_entity_returns_201(client):
    response = client.post(
        "/api/v1/graph/entities",
        json={"id": "bts:1", "type": "BTS", "name": "BTS Kinshasa 1", "properties": {"puissance": 40}},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["id"] == "bts:1"


def test_create_entity_missing_field_returns_400(client):
    response = client.post("/api/v1/graph/entities", json={"type": "BTS", "name": "BTS 1"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_get_entity_returns_created_entity(client):
    client.post("/api/v1/graph/entities", json={"id": "bts:1", "type": "BTS", "name": "BTS 1"})

    response = client.get("/api/v1/graph/entities/bts:1")

    assert response.status_code == 200
    assert response.get_json()["data"]["name"] == "BTS 1"


def test_get_entity_returns_404_when_absent(client):
    response = client.get("/api/v1/graph/entities/inconnu")

    assert response.status_code == 404


def test_delete_entity_removes_it(client):
    client.post("/api/v1/graph/entities", json={"id": "bts:1", "type": "BTS", "name": "BTS 1"})

    delete_response = client.delete("/api/v1/graph/entities/bts:1")
    get_response = client.get("/api/v1/graph/entities/bts:1")

    assert delete_response.status_code == 200
    assert get_response.status_code == 404


def test_create_relationship_between_existing_entities_returns_201(client):
    client.post("/api/v1/graph/entities", json={"id": "bts:1", "type": "BTS", "name": "BTS 1"})
    client.post("/api/v1/graph/entities", json={"id": "bsc:1", "type": "BSC", "name": "BSC 1"})

    response = client.post(
        "/api/v1/graph/relationships",
        json={"source_id": "bts:1", "target_id": "bsc:1", "type": "CONNECTED_TO"},
    )

    assert response.status_code == 201


def test_create_relationship_with_missing_entity_returns_400(client):
    client.post("/api/v1/graph/entities", json={"id": "bts:1", "type": "BTS", "name": "BTS 1"})

    response = client.post(
        "/api/v1/graph/relationships",
        json={"source_id": "bts:1", "target_id": "bsc:inconnu", "type": "CONNECTED_TO"},
    )

    assert response.status_code == 400
    assert "bsc:inconnu" in response.get_json()["error"]


def test_get_related_entities_returns_connected_entity(client):
    client.post("/api/v1/graph/entities", json={"id": "bts:1", "type": "BTS", "name": "BTS 1"})
    client.post("/api/v1/graph/entities", json={"id": "bsc:1", "type": "BSC", "name": "BSC 1"})
    client.post(
        "/api/v1/graph/relationships",
        json={"source_id": "bts:1", "target_id": "bsc:1", "type": "CONNECTED_TO"},
    )

    response = client.get("/api/v1/graph/entities/bts:1/related")

    assert response.status_code == 200
    results = response.get_json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["id"] == "bsc:1"


def test_get_related_entities_returns_404_when_entity_absent(client):
    response = client.get("/api/v1/graph/entities/inconnu/related")

    assert response.status_code == 404
