import math

import pytest

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.modules.retrieval.contracts import VectorSearchResult
from app.modules.validation.confidence_scorer import ConfidenceScorer
from app.modules.validation.contradiction_detector import ContradictionDetector
from app.modules.validation.repository import ValidationRepository
from app.modules.validation.service import ValidationService


# ---------- ConfidenceScorer ----------

def test_confidence_scorer_returns_zero_for_no_results():
    assert ConfidenceScorer().score([]) == 0.0


def test_confidence_scorer_returns_zero_when_no_score_available():
    results = [VectorSearchResult(id="a", document="x", metadata={}, distance=None)]
    assert ConfidenceScorer().score(results) == 0.0


def test_confidence_scorer_applies_sigmoid_to_top_score():
    results = [VectorSearchResult(id="a", document="x", metadata={}, distance=2.0)]
    expected = 1.0 / (1.0 + math.exp(-2.0))
    assert ConfidenceScorer().score(results) == pytest.approx(expected)


def test_confidence_scorer_uses_only_top_result():
    results = [
        VectorSearchResult(id="a", document="x", metadata={}, distance=5.0),
        VectorSearchResult(id="b", document="y", metadata={}, distance=-5.0),
    ]
    # Résultats déjà triés par pertinence (reranker) : seul le premier compte.
    assert ConfidenceScorer().score(results) > 0.9


# ---------- ContradictionDetector (avec vraie DB SQLite) ----------

@pytest.fixture
def app_context():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _make_version(document_id, version_number):
    v = DocumentVersion(
        document_id=document_id, version=version_number, status=DocumentStatus.ACTIVE, storage_path="/tmp/x.txt"
    )
    db.session.add(v)
    db.session.flush()
    return v


def test_contradiction_detector_returns_empty_for_single_version_per_document(app_context):
    document = Document(title="Doc")
    db.session.add(document)
    db.session.flush()
    v1 = _make_version(document.id, 1)
    db.session.commit()

    results = [VectorSearchResult(id="a", document="x", metadata={"document_version_id": v1.id})]

    warnings = ContradictionDetector().detect(results)

    assert warnings == []


def test_contradiction_detector_flags_multiple_versions_of_same_document(app_context):
    document = Document(title="Doc")
    db.session.add(document)
    db.session.flush()
    v1 = _make_version(document.id, 1)
    v2 = _make_version(document.id, 2)
    db.session.commit()

    results = [
        VectorSearchResult(id="a", document="x", metadata={"document_version_id": v1.id}),
        VectorSearchResult(id="b", document="y", metadata={"document_version_id": v2.id}),
    ]

    warnings = ContradictionDetector().detect(results)

    assert len(warnings) == 1
    assert str(document.id) in warnings[0]


def test_contradiction_detector_ignores_results_without_metadata(app_context):
    warnings = ContradictionDetector().detect([VectorSearchResult(id="a", document="x", metadata={})])
    assert warnings == []


# ---------- ValidationService ----------

def test_validation_service_abstains_below_confidence_threshold():
    results = [VectorSearchResult(id="a", document="x", metadata={}, distance=-10.0)]
    service = ValidationService(confidence_threshold=0.5)

    outcome = service.validate(results)

    assert outcome.should_abstain is True
    assert outcome.abstain_reason is not None
    assert "Confiance insuffisante" in outcome.abstain_reason


def test_validation_service_proceeds_above_confidence_threshold():
    results = [VectorSearchResult(id="a", document="x", metadata={}, distance=10.0)]
    service = ValidationService(confidence_threshold=0.5)

    outcome = service.validate(results)

    assert outcome.should_abstain is False
    assert outcome.abstain_reason is None
    assert outcome.confidence > 0.5


def test_validation_service_includes_contradiction_warnings(app_context):
    document = Document(title="Doc")
    db.session.add(document)
    db.session.flush()
    v1 = _make_version(document.id, 1)
    v2 = _make_version(document.id, 2)
    db.session.commit()

    results = [
        VectorSearchResult(id="a", document="x", metadata={"document_version_id": v1.id}, distance=10.0),
        VectorSearchResult(id="b", document="y", metadata={"document_version_id": v2.id}, distance=9.0),
    ]
    service = ValidationService(confidence_threshold=0.5)

    outcome = service.validate(results)

    assert outcome.should_abstain is False  # confiance suffisante malgré l'alerte
    assert len(outcome.warnings) == 1
