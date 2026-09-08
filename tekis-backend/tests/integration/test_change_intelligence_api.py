"""
`ChangeIntelligenceRepository` utilise l'ORM standard : ces tests tournent sur le
SQLite en mémoire par défaut de `TestingConfig`, pas de PostgreSQL réel nécessaire
ici. `Neo4jGraphStore` est monkeypatché (aucun serveur Neo4j disponible, memoire.md
§26) pour vérifier le câblage optionnel de l'analyse d'impact.
"""
import pytest

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.chunk import Chunk
from app.modules.knowledge_graph.contracts import GraphEntity


class InMemoryGraphStore:
    _entities: dict = {}

    def __init__(self, uri=None, user=None, password=None):
        pass

    def get_entity(self, entity_id):
        return InMemoryGraphStore._entities.get(entity_id)

    def get_related_entities(self, entity_id, relationship_type=None, depth=1):
        return []

    def find_entities_by_source_chunk_ids(self, chunk_ids):
        return [e for e in InMemoryGraphStore._entities.values() if set(e.source_chunk_ids) & set(chunk_ids)]

    def upsert_entity(self, entity):
        InMemoryGraphStore._entities[entity.id] = entity

    def upsert_relationship(self, relationship):
        pass

    def delete_entity(self, entity_id):
        InMemoryGraphStore._entities.pop(entity_id, None)


@pytest.fixture(autouse=True)
def reset_store():
    InMemoryGraphStore._entities = {}
    yield


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setattr("app.api.change_intelligence.Neo4jGraphStore", InMemoryGraphStore)
    flask_app = create_app("testing")
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _seed_two_versions(app, chunks_v1, chunks_v2):
    with app.app_context():
        document = Document(title="Doc test API")
        db.session.add(document)
        db.session.flush()

        v1 = DocumentVersion(
            document_id=document.id, version=1, status=DocumentStatus.SUPERSEDED,
            storage_path="/tmp/v1.txt", original_filename="v1.txt", file_type="txt",
        )
        db.session.add(v1)
        db.session.flush()
        chunk_ids_v1 = []
        for i, content in enumerate(chunks_v1):
            c = Chunk(document_version_id=v1.id, content=content, position=i, content_hash=content)
            db.session.add(c)
            db.session.flush()
            chunk_ids_v1.append(c.id)

        v2 = DocumentVersion(
            document_id=document.id, version=2, status=DocumentStatus.ACTIVE,
            storage_path="/tmp/v2.txt", original_filename="v2.txt", file_type="txt",
        )
        db.session.add(v2)
        db.session.flush()
        chunk_ids_v2 = []
        for i, content in enumerate(chunks_v2):
            c = Chunk(document_version_id=v2.id, content=content, position=i, content_hash=content)
            db.session.add(c)
            db.session.flush()
            chunk_ids_v2.append(c.id)

        db.session.commit()
        return document.id, chunk_ids_v1, chunk_ids_v2


def test_compare_endpoint_returns_diff(client, app):
    document_id, _, _ = _seed_two_versions(
        app,
        ["Section stable.", "Contenu original ici présent."],
        ["Section stable.", "Nouvelle section totalement inédite."],
    )

    response = client.post("/api/v1/change-intelligence/compare", json={"document_id": document_id})

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    comparison = body["data"]["comparison"]
    assert comparison["version_from"] == 1
    assert comparison["version_to"] == 2
    assert comparison["unchanged_count"] == 1


def test_compare_endpoint_missing_document_id_returns_400(client):
    response = client.post("/api/v1/change-intelligence/compare", json={})

    assert response.status_code == 400


def test_compare_endpoint_unknown_document_returns_404(client):
    response = client.post("/api/v1/change-intelligence/compare", json={"document_id": 999999})

    assert response.status_code == 404


def test_compare_endpoint_includes_impact_when_graph_entity_linked(client, app):
    document_id, chunk_ids_v1, chunk_ids_v2 = _seed_two_versions(
        app,
        ["Contenu original de la procédure ici présent en entier."],
        ["Contenu totalement différent xylophone kangourou nébuleuse orage."],
    )

    with app.app_context():
        store = InMemoryGraphStore()
        store.upsert_entity(
            GraphEntity(id="proc:1", type="Procedure", name="Procédure liée", source_chunk_ids=[chunk_ids_v1[0]])
        )

    response = client.post("/api/v1/change-intelligence/compare", json={"document_id": document_id})

    assert response.status_code == 200
    impact = response.get_json()["data"]["impact"]
    assert impact is not None
    assert any(e["entity_id"] == "proc:1" for e in impact["directly_linked_entities"])


def test_compare_endpoint_can_disable_impact_analysis(client, app):
    document_id, _, _ = _seed_two_versions(app, ["A contenu."], ["B contenu différent."])

    response = client.post(
        "/api/v1/change-intelligence/compare",
        json={"document_id": document_id, "include_impact": False},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["impact"] is None
