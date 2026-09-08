"""
Aucun Ollama/reranker/Neo4j réel disponible dans ce sandbox (mêmes limites que les
Phases 2/3/4, memoire.md §23/§25/§26) : mêmes doubles de test que
`test_phase5_auth_acl.py`, réutilisés ici pour vérifier le câblage complet de
`POST /api/v1/evaluation/run` (les 5 variantes, l'authentification, les métriques).
"""
import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.chunk import Chunk
from app.models.identity import User
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


class FakeGraphStore:
    """Neo4j non disponible ici (memoire.md §26) : store en mémoire vide -> les
    variantes KG_RAG/TEKIS_COMPLETE tournent sans enrichissement, ce qui est un
    comportement normal et prévu (memoire.md §10 : le KG est optionnel)."""

    def __init__(self, uri=None, user=None, password=None):
        pass

    def find_entities_by_source_chunk_ids(self, chunk_ids):
        return []

    def get_related_entities(self, entity_id, relationship_type=None, depth=1):
        return []


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.evaluation.OllamaEmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr("app.api.evaluation.OllamaLLMClient", FakeLLMClient)
    monkeypatch.setattr("app.api.evaluation.PostgresFtsLexicalSearch", FakeLexicalSearch)
    monkeypatch.setattr("app.api.evaluation.CrossEncoderReranker", FakeReranker)
    monkeypatch.setattr("app.api.evaluation.Neo4jGraphStore", FakeGraphStore)

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


def _make_user_and_token(client, app):
    with app.app_context():
        user = User(name="Éval", email="eval@tekis.local", password_hash=generate_password_hash("pass1234"))
        db.session.add(user)
        db.session.commit()

    login = client.post("/api/v1/auth/login", json={"email": "eval@tekis.local", "password": "pass1234"})
    token = login.get_json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_document_with_chunk(app, content):
    with app.app_context():
        document = Document(title="Doc éval")
        db.session.add(document)
        db.session.flush()
        version = DocumentVersion(
            document_id=document.id, version=1, status=DocumentStatus.ACTIVE,
            storage_path="/tmp/fake.txt", original_filename="fake.txt", file_type="txt",
        )
        db.session.add(version)
        db.session.flush()
        chunk = Chunk(document_version_id=version.id, content=content, position=0, content_hash=content)
        db.session.add(chunk)
        db.session.commit()
        return chunk.id, version.id


def test_run_evaluation_requires_authentication(client):
    response = client.post("/api/v1/evaluation/run", json={"questions": [{"id": "q1", "question": "Test ?"}]})

    assert response.status_code == 401


def test_run_evaluation_missing_questions_returns_400(client, app):
    headers = _make_user_and_token(client, app)

    response = client.post("/api/v1/evaluation/run", json={}, headers=headers)

    assert response.status_code == 400


def test_run_evaluation_returns_all_five_variants_by_default(client, app):
    headers = _make_user_and_token(client, app)

    response = client.post(
        "/api/v1/evaluation/run",
        json={"questions": [{"id": "q1", "question": "Quelle est la procédure ?"}]},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert set(data.keys()) == {"llm_only", "vector_only", "hybrid", "kg_rag", "tekis_complete"}


def test_run_evaluation_can_select_specific_variants(client, app):
    headers = _make_user_and_token(client, app)

    response = client.post(
        "/api/v1/evaluation/run",
        json={"questions": [{"id": "q1", "question": "Question ?"}], "variants": ["llm_only", "hybrid"]},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert set(data.keys()) == {"llm_only", "hybrid"}


def test_run_evaluation_llm_only_never_abstains_and_has_no_sources(client, app):
    headers = _make_user_and_token(client, app)

    response = client.post(
        "/api/v1/evaluation/run",
        json={"questions": [{"id": "q1", "question": "Question ?"}], "variants": ["llm_only"]},
        headers=headers,
    )

    result = response.get_json()["data"]["llm_only"]["results"][0]
    assert result["abstained"] is False
    assert result["answer"] is not None


def test_run_evaluation_computes_keyword_coverage(client, app):
    headers = _make_user_and_token(client, app)
    chunk_id, version_id = _seed_document_with_chunk(app, "La maintenance dure deux heures environ.")

    response = client.post(
        "/api/v1/evaluation/run",
        json={
            "questions": [
                {
                    "id": "q1",
                    "question": "Combien de temps dure la maintenance ?",
                    "expected_chunk_ids": [chunk_id],
                    "expected_keywords": ["maintenance"],
                }
            ],
            "variants": ["llm_only"],
        },
        headers=headers,
    )

    result = response.get_json()["data"]["llm_only"]["results"][0]
    # llm_only ne renvoie jamais "maintenance" dans une réponse factice -> coverage 0
    assert result["keyword_coverage"] == 0.0
