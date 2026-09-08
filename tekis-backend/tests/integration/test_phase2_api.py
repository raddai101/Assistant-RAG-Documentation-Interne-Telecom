"""
Tests d'intégration Phase 2 (search/chat/reindex). Ollama n'existe pas dans ce
sandbox : les classes `OllamaEmbeddingClient` / `OllamaLLMClient` sont monkeypatchées
à l'endroit où les blueprints les importent, pour vérifier le câblage HTTP -> service
-> réponse JSON sans dépendre d'un serveur externe.

Depuis la Phase 3, `search`/`chat` utilisent `HybridRetrievalService`
(fusion lexicale + reranking). Ces tests hérités de la Phase 2 monkeypatchent aussi
`PostgresFtsLexicalSearch` (aucune correspondance lexicale — le scénario ne teste
que le chemin vectoriel, volontairement inchangé) et `CrossEncoderReranker` (passe-
plat qui préserve l'ordre de fusion) pour rester portables sans PostgreSQL réel ni
modèle cross-encoder téléchargé. La recherche lexicale réelle (PostgreSQL FTS) et la
fusion sont testées séparément dans `test_hybrid_retrieval_real_postgres.py`. La
vérification avec un Ollama et un reranker réels reste à faire par Radda101 sur son
infrastructure (memoire.md §24).

Depuis la Phase 5, `/search` et `/chat` exigent une identité (`require_auth`). Ces
tests utilisent un utilisateur de rôle `admin` (bypass ACL, memoire.md §27) pour
continuer à tester le chemin RAG lui-même sans complexifier chaque scénario avec des
`Permission` explicites — le filtrage ACL fin est testé séparément dans
`test_access_control_service.py` et `tests/integration/test_phase5_auth_acl.py`.
"""
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.chunk import Chunk
from app.models.identity import User, Role
from app.modules.identity.jwt_service import JWTService
from app.modules.retrieval.reranker.contracts import RerankedResult


class FakeEmbeddingClient:
    def __init__(self, base_url=None, model=None):
        pass

    def embed(self, texts):
        return [[float(len(t))] for t in texts]


class FakeLLMClient:
    def __init__(self, base_url=None, model=None):
        pass

    def generate(self, prompt):
        return "Réponse factice générée à partir du contexte fourni."


class FakeLexicalSearch:
    """Aucune correspondance lexicale : ces tests héritent de la Phase 2 et ne
    vérifient que le chemin vectoriel."""

    def __init__(self):
        pass

    def search(self, query, top_k, document_version_ids=None):
        return []


class FakeReranker:
    """Passe-plat : préserve l'ordre déjà établi par la fusion RRF, sans dépendre
    d'un modèle cross-encoder réel (non disponible dans ce sandbox)."""

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
    monkeypatch.setattr("app.api.chat.OllamaEmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr("app.api.chat.OllamaLLMClient", FakeLLMClient)
    monkeypatch.setattr("app.api.search.PostgresFtsLexicalSearch", FakeLexicalSearch)
    monkeypatch.setattr("app.api.chat.PostgresFtsLexicalSearch", FakeLexicalSearch)
    monkeypatch.setattr("app.api.search.CrossEncoderReranker", FakeReranker)
    monkeypatch.setattr("app.api.chat.CrossEncoderReranker", FakeReranker)

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


@pytest.fixture
def auth_headers(app):
    """Utilisateur admin (bypass ACL, memoire.md §27) : un `Authorization: Bearer
    <token>` valide, prêt à l'emploi pour les tests qui ne portent pas sur l'ACL
    elle-même."""
    with app.app_context():
        role = Role(name="admin")
        db.session.add(role)
        db.session.flush()
        user = User(
            name="Admin Test",
            email="admin@tekis.local",
            password_hash=generate_password_hash("irrelevant"),
            role=role,
        )
        db.session.add(user)
        db.session.commit()
        token = JWTService(
            secret_key=app.config["JWT_SECRET_KEY"],
            expires_minutes=app.config["JWT_ACCESS_TOKEN_EXPIRES_MINUTES"],
        ).encode(user)
    return {"Authorization": f"Bearer {token}"}


def _seed_document_with_chunk(content="Procédure SGSN-2024-17 pour la maintenance réseau."):
    document = Document(title="Procédure SGSN")
    db.session.add(document)
    db.session.flush()
    version = DocumentVersion(
        document_id=document.id,
        version=1,
        status=DocumentStatus.ACTIVE,
        storage_path="/tmp/fake.txt",
        original_filename="fake.txt",
        file_type="txt",
    )
    db.session.add(version)
    db.session.flush()
    chunk = Chunk(
        document_version_id=version.id, content=content, position=0, content_hash="h1", page=1
    )
    db.session.add(chunk)
    db.session.commit()
    return document, version, chunk


def test_reindex_endpoint_indexes_pending_chunks(app, client):
    with app.app_context():
        _seed_document_with_chunk()

    response = client.post("/api/v1/embeddings/reindex", json={})

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["num_chunks_indexed"] == 1


def test_reindex_endpoint_is_idempotent(app, client):
    with app.app_context():
        _seed_document_with_chunk()

    first = client.post("/api/v1/embeddings/reindex", json={})
    second = client.post("/api/v1/embeddings/reindex", json={})

    assert first.get_json()["data"]["num_chunks_indexed"] == 1
    assert second.get_json()["data"]["num_chunks_indexed"] == 0


def test_search_endpoint_requires_authentication(client):
    # Phase 5 : IDENTITÉ est le premier maillon du pipeline (§15) — sans token,
    # 401 avant même la validation du corps de la requête.
    response = client.post("/api/v1/search", json={"query": "peu importe"})
    assert response.status_code == 401
    assert response.get_json()["success"] is False


def test_search_endpoint_requires_query(client, auth_headers):
    response = client.post("/api/v1/search", json={}, headers=auth_headers)
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_search_endpoint_returns_indexed_chunk(app, client, auth_headers):
    with app.app_context():
        _seed_document_with_chunk("Contenu unique à retrouver via la recherche.")
    client.post("/api/v1/embeddings/reindex", json={})

    response = client.post(
        "/api/v1/search", json={"query": "Contenu unique à retrouver"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert len(body["data"]["results"]) == 1
    assert "Contenu unique" in body["data"]["results"][0]["content"]


def test_chat_endpoint_requires_authentication(client):
    response = client.post("/api/v1/chat", json={"query": "peu importe"})
    assert response.status_code == 401


def test_chat_endpoint_requires_query(client, auth_headers):
    response = client.post("/api/v1/chat", json={}, headers=auth_headers)
    assert response.status_code == 400


def test_chat_endpoint_returns_sourced_answer_after_indexing(app, client, auth_headers):
    with app.app_context():
        _seed_document_with_chunk("La procédure de maintenance BTS impose une coupure planifiée.")
    client.post("/api/v1/embeddings/reindex", json={})

    response = client.post(
        "/api/v1/chat",
        json={"query": "Quelle est la procédure de maintenance BTS ?"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["abstained"] is False
    assert body["data"]["answer"] == "Réponse factice générée à partir du contexte fourni."
    assert len(body["data"]["sources"]) == 1
    # Phase 6 : la validation evidence-first expose sa confiance et ses alertes.
    assert 0.0 <= body["data"]["confidence"] <= 1.0
    assert body["data"]["confidence"] > 0.5  # FakeReranker renvoie un score de 1.0
    assert body["data"]["warnings"] == []


def test_chat_endpoint_abstains_when_corpus_empty(client, auth_headers):
    # Aucun chunk indexé -> aucune preuve -> abstention obligatoire (§17 instructions)
    response = client.post(
        "/api/v1/chat", json={"query": "Question sans corpus indexé ?"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["data"]["abstained"] is True
    assert body["data"]["answer"] is None
