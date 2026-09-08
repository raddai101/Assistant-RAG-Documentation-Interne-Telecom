"""
Tests avec un **vrai serveur PostgreSQL** (installé localement dans cet
environnement de développement pour cette phase, memoire.md §24) — contrairement
aux autres tests du projet qui utilisent SQLite en mémoire (`to_tsvector` et
`websearch_to_tsquery` n'existent pas sur SQLite, donc `PostgresFtsLexicalSearch` ne
peut être vérifié qu'avec un vrai Postgres).

Prérequis pour lancer ces tests : un PostgreSQL accessible sur
`postgresql://tekis_user:tekis_pass@localhost:5432/tekis_test` (voir memoire.md §24
pour la commande d'installation utilisée). Si indisponible, ces tests échoueront à
la connexion — c'est un signal clair, pas une erreur masquée.
"""
import pytest

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.chunk import Chunk
from app.modules.retrieval.lexical.postgres_fts import PostgresFtsLexicalSearch
from app.modules.retrieval.hybrid_service import HybridRetrievalService
from app.modules.retrieval.contracts import VectorSearchResult
from app.modules.retrieval.reranker.contracts import RerankedResult

REAL_POSTGRES_URL = "postgresql://tekis_user:tekis_pass@localhost:5432/tekis_test"


@pytest.fixture
def app():
    flask_app = create_app("testing", config_overrides={"SQLALCHEMY_DATABASE_URI": REAL_POSTGRES_URL})
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


def _seed_chunk(content: str) -> Chunk:
    document = Document(title="Doc test FTS")
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
    chunk = Chunk(document_version_id=version.id, content=content, position=0, content_hash="h", page=1)
    db.session.add(chunk)
    db.session.commit()
    return chunk


def test_lexical_search_finds_matching_chunk_by_keyword(app):
    with app.app_context():
        _seed_chunk("La procédure de maintenance du réseau mobile impose une coupure planifiée.")
        _seed_chunk("Le contrat de service client concerne la facturation mensuelle.")

        results = PostgresFtsLexicalSearch().search("maintenance réseau", top_k=5)

        assert len(results) == 1
        assert "maintenance" in results[0].content


def test_lexical_search_finds_exact_technical_identifier(app):
    """Vérifie la justification métier du FTS (memoire.md §9) : un identifiant exact
    type SGSN-2024-17 doit être trouvable, ce qu'une recherche purement vectorielle
    échoue à faire de manière fiable."""
    with app.app_context():
        _seed_chunk("Se référer à la procédure SGSN-2024-17 pour la reconfiguration.")
        _seed_chunk("Aucun rapport avec l'identifiant recherché dans ce chunk.")

        results = PostgresFtsLexicalSearch().search("SGSN-2024-17", top_k=5)

        assert len(results) >= 1
        assert "SGSN-2024-17" in results[0].content


def test_lexical_search_ranks_more_relevant_chunk_higher(app):
    with app.app_context():
        _seed_chunk("Antenne. Un mot antenne isolé, sans plus de contexte antenne.")
        _seed_chunk("Ce document ne parle pas du tout du sujet recherché.")

        results = PostgresFtsLexicalSearch().search("antenne", top_k=5)

        assert len(results) == 1  # seul le premier chunk contient le terme
        assert results[0].rank > 0


def test_lexical_search_returns_empty_when_no_match(app):
    with app.app_context():
        _seed_chunk("Contenu sans rapport avec la requête.")

        results = PostgresFtsLexicalSearch().search("kubernetes", top_k=5)

        assert results == []


class _FakeEmbeddingClient:
    def embed(self, texts):
        return [[0.0] for _ in texts]


class _EmptyVectorStore:
    def search(self, query_embedding, top_k, where=None):
        return []  # ce test vérifie le canal lexical seul


class _PassthroughReranker:
    def rerank(self, query, candidates, top_k):
        return [
            RerankedResult(chunk_id=c.chunk_id, content=c.content, metadata=c.metadata, score=1.0 - i * 0.01)
            for i, c in enumerate(candidates[:top_k])
        ]


def test_hybrid_service_returns_lexical_only_result_via_real_postgres(app):
    """Bout-en-bout : HybridRetrievalService avec vecteur vide (ChromaDB non
    sollicité ici) mais recherche lexicale réelle sur PostgreSQL — vérifie que le
    canal lexical seul suffit à faire remonter un résultat pertinent."""
    with app.app_context():
        chunk = _seed_chunk("La configuration du MPLS nécessite une validation préalable.")

        service = HybridRetrievalService(
            embedding_client=_FakeEmbeddingClient(),
            vector_store=_EmptyVectorStore(),
            lexical_search=PostgresFtsLexicalSearch(),
            reranker=_PassthroughReranker(),
        )

        result = service.search("configuration MPLS")

        assert len(result.results) == 1
        assert isinstance(result.results[0], VectorSearchResult)
        assert result.results[0].metadata["chunk_id"] == chunk.id
        assert "MPLS" in result.results[0].document
