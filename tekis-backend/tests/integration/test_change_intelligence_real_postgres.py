"""
`ChangeIntelligenceRepository` utilise l'ORM SQLAlchemy standard (pas de SQL brut
PostgreSQL-spécifique comme `PostgresFtsLexicalSearch`) — ces tests pourraient donc
tourner sur SQLite. On les fait néanmoins tourner sur le vrai PostgreSQL déjà mis en
place pour la Phase 3 (memoire.md §24), par cohérence avec l'objectif de vérifier le
pipeline complet en conditions aussi réelles que possible quand c'est peu coûteux.
"""
import pytest

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.chunk import Chunk
from app.modules.change_intelligence.repository import (
    ChangeIntelligenceRepository,
    DocumentVersionNotFoundError,
)
from app.modules.change_intelligence.service import ChangeIntelligenceService
from app.modules.change_intelligence.contracts import ChangeType

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


def _create_version(document, version_number, chunks_content, status=DocumentStatus.ACTIVE):
    version = DocumentVersion(
        document_id=document.id,
        version=version_number,
        status=status,
        storage_path=f"/tmp/fake-v{version_number}.txt",
        original_filename="fake.txt",
        file_type="txt",
    )
    db.session.add(version)
    db.session.flush()
    for i, content in enumerate(chunks_content):
        chunk = Chunk(
            document_version_id=version.id,
            content=content,
            position=i,
            content_hash=content,  # simplifié pour les tests : hash = contenu
        )
        db.session.add(chunk)
    db.session.commit()
    return version


def test_compare_latest_two_versions_detects_changes(app):
    with app.app_context():
        document = Document(title="Procédure SGSN")
        db.session.add(document)
        db.session.flush()

        _create_version(
            document,
            1,
            ["Section stable inchangée dans toutes les versions.", "La maintenance dure deux heures environ."],
            status=DocumentStatus.SUPERSEDED,
        )
        _create_version(
            document,
            2,
            ["Section stable inchangée dans toutes les versions.", "La maintenance dure trois heures environ.", "Nouvelle section ajoutée récemment."],
        )

        service = ChangeIntelligenceService(repository=ChangeIntelligenceRepository())
        result = service.compare_versions(document.id)

        assert result.version_from == 1
        assert result.version_to == 2
        assert result.unchanged_count == 1
        assert len(result.modifications) == 1
        assert len(result.additions) == 1
        assert len(result.removals) == 0


def test_compare_explicit_versions(app):
    with app.app_context():
        document = Document(title="Norme antenne")
        db.session.add(document)
        db.session.flush()
        _create_version(document, 1, ["Contenu version 1."], status=DocumentStatus.SUPERSEDED)
        _create_version(document, 2, ["Contenu version 2."])

        service = ChangeIntelligenceService(repository=ChangeIntelligenceRepository())
        result = service.compare_versions(document.id, version_from=1, version_to=2)

        assert result.version_from == 1
        assert result.version_to == 2


def test_compare_raises_when_document_not_found(app):
    with app.app_context():
        service = ChangeIntelligenceService(repository=ChangeIntelligenceRepository())

        with pytest.raises(DocumentVersionNotFoundError):
            service.compare_versions(document_id=999999)


def test_compare_raises_when_only_one_version_exists(app):
    with app.app_context():
        document = Document(title="Document unique version")
        db.session.add(document)
        db.session.flush()
        _create_version(document, 1, ["Seul contenu existant."])

        service = ChangeIntelligenceService(repository=ChangeIntelligenceRepository())

        with pytest.raises(DocumentVersionNotFoundError, match="moins de deux versions"):
            service.compare_versions(document.id)


def test_compare_raises_when_explicit_version_not_found(app):
    with app.app_context():
        document = Document(title="Doc test")
        db.session.add(document)
        db.session.flush()
        _create_version(document, 1, ["Contenu."], status=DocumentStatus.SUPERSEDED)
        _create_version(document, 2, ["Contenu v2."])

        service = ChangeIntelligenceService(repository=ChangeIntelligenceRepository())

        with pytest.raises(DocumentVersionNotFoundError, match="99"):
            service.compare_versions(document.id, version_from=1, version_to=99)


def test_analyze_impact_returns_none_without_impact_service(app):
    with app.app_context():
        document = Document(title="Doc sans graphe")
        db.session.add(document)
        db.session.flush()
        _create_version(document, 1, ["A"], status=DocumentStatus.SUPERSEDED)
        _create_version(document, 2, ["B"])

        service = ChangeIntelligenceService(repository=ChangeIntelligenceRepository())
        comparison = service.compare_versions(document.id)

        assert service.analyze_impact(comparison) is None
