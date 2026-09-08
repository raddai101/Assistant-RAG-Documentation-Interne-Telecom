"""
Tests d'intégration Phase 5 : authentification réelle (`POST /api/v1/auth/login`) et
filtrage ACL bout en bout sur `/api/v1/search` (§12, §15). Mêmes fakes Ollama/lexical/
reranker que `test_phase2_api.py` — cette phase ne change rien au pipeline RAG
lui-même, seulement ce qu'il a le droit de voir.
"""
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus, Permission
from app.models.chunk import Chunk
from app.models.identity import User, Role, Department
from app.modules.retrieval.reranker.contracts import RerankedResult


class FakeEmbeddingClient:
    def __init__(self, base_url=None, model=None):
        pass

    def embed(self, texts):
        return [[float(len(t))] for t in texts]


class FakeLexicalSearch:
    def __init__(self):
        pass

    def search(self, query, top_k, document_version_ids=None):
        return []


class FakeReranker:
    def __init__(self, model_name=None):
        pass

    def rerank(self, query, candidates, top_k):
        return [
            RerankedResult(chunk_id=c.chunk_id, content=c.content, metadata=c.metadata, score=1.0 - i * 0.01)
            for i, c in enumerate(candidates[:top_k])
        ]


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.embeddings.OllamaEmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr("app.api.search.OllamaEmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr("app.api.search.PostgresFtsLexicalSearch", FakeLexicalSearch)
    monkeypatch.setattr("app.api.search.CrossEncoderReranker", FakeReranker)

    flask_app = create_app("testing")
    flask_app.config["CHROMA_PERSIST_DIR"] = str(tmp_path / "chroma")
    flask_app.config["CHROMA_COLLECTION_NAME"] = "test_collection"
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_user(email, password, role_name=None, department_id=None):
    role = None
    if role_name:
        role = db.session.query(Role).filter_by(name=role_name).first()
        if role is None:
            role = Role(name=role_name)
            db.session.add(role)
            db.session.flush()
    user = User(
        name=email,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        department_id=department_id,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _seed_document(content, allowed_roles=None):
    document = Document(title="Doc")
    db.session.add(document)
    db.session.flush()
    version = DocumentVersion(
        document_id=document.id, version=1, status=DocumentStatus.ACTIVE, storage_path="/tmp/f.txt"
    )
    db.session.add(version)
    db.session.flush()
    chunk = Chunk(document_version_id=version.id, content=content, position=0, content_hash="h", page=1)
    db.session.add(chunk)
    if allowed_roles is not None:
        db.session.add(
            Permission(document_id=document.id, allowed_roles=allowed_roles, allowed_users=[], allowed_departments=[])
        )
    db.session.commit()
    return document, version, chunk


def _login(client, email, password):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response


def test_login_returns_valid_token_for_correct_credentials(app, client):
    with app.app_context():
        _make_user("alice@tekis.local", "secret123")

    response = _login(client, "alice@tekis.local", "secret123")

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["access_token"]
    assert body["data"]["user"]["email"] == "alice@tekis.local"


def test_login_rejects_wrong_password(app, client):
    with app.app_context():
        _make_user("alice@tekis.local", "secret123")

    response = _login(client, "alice@tekis.local", "wrong")

    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_login_requires_email_and_password(client):
    response = client.post("/api/v1/auth/login", json={"email": "a@b.com"})
    assert response.status_code == 400


def test_search_with_token_only_returns_documents_user_is_authorized_for(app, client):
    with app.app_context():
        _seed_document("Contenu réseau visible par le rôle reseau", allowed_roles=["reseau"])
        _seed_document("Contenu RH invisible pour le rôle reseau", allowed_roles=["rh"])
        _make_user("bob@tekis.local", "secret123", role_name="reseau")

    login_response = _login(client, "bob@tekis.local", "secret123")
    token = login_response.get_json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/embeddings/reindex", json={})

    response = client.post(
        "/api/v1/search", json={"query": "Contenu", "top_k": 10}, headers=headers
    )

    assert response.status_code == 200
    contents = [r["content"] for r in response.get_json()["data"]["results"]]
    assert any("réseau" in c for c in contents)
    assert all("RH invisible" not in c for c in contents)


def test_search_returns_empty_for_user_with_no_permissions(app, client):
    with app.app_context():
        _seed_document("Contenu quelconque", allowed_roles=["reseau"])
        _make_user("carla@tekis.local", "secret123", role_name="marketing")

    login_response = _login(client, "carla@tekis.local", "secret123")
    token = login_response.get_json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/embeddings/reindex", json={})

    response = client.post("/api/v1/search", json={"query": "Contenu"}, headers=headers)

    assert response.status_code == 200
    assert response.get_json()["data"]["results"] == []


def test_search_rejects_invalid_token(client):
    response = client.post(
        "/api/v1/search", json={"query": "x"}, headers={"Authorization": "Bearer invalide"}
    )
    assert response.status_code == 401


def test_search_with_as_of_respects_temporal_validity(app, client):
    with app.app_context():
        document = Document(title="Norme")
        db.session.add(document)
        db.session.flush()
        now = datetime.now(timezone.utc)
        old_version = DocumentVersion(
            document_id=document.id,
            version=1,
            status=DocumentStatus.SUPERSEDED,
            storage_path="/tmp/old.txt",
            valid_from=now - timedelta(days=30),
            valid_to=now - timedelta(days=1),
        )
        db.session.add(old_version)
        db.session.flush()
        db.session.add(Chunk(document_version_id=old_version.id, content="Ancienne norme réseau", position=0, content_hash="h1", page=1))
        db.session.add(Permission(document_id=document.id, allowed_roles=["reseau"], allowed_users=[], allowed_departments=[]))
        db.session.commit()
        _make_user("dan@tekis.local", "secret123", role_name="reseau")

    login_response = _login(client, "dan@tekis.local", "secret123")
    token = login_response.get_json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/embeddings/reindex", json={})

    as_of_last_week = (now - timedelta(days=15)).isoformat()
    response_valid_period = client.post(
        "/api/v1/search", json={"query": "norme", "as_of": as_of_last_week}, headers=headers
    )
    response_today = client.post("/api/v1/search", json={"query": "norme"}, headers=headers)

    assert len(response_valid_period.get_json()["data"]["results"]) == 1
    assert len(response_today.get_json()["data"]["results"]) == 0
