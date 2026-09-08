from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.modules.governance.temporal_resolver import TemporalResolver


@pytest.fixture
def app_context():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _make_document():
    document = Document(title="Procédure temporelle")
    db.session.add(document)
    db.session.flush()
    return document


def test_falls_back_to_active_status_when_no_temporal_fields_set(app_context):
    document = _make_document()
    active = DocumentVersion(
        document_id=document.id, version=1, status=DocumentStatus.ACTIVE, storage_path="/tmp/a.txt"
    )
    superseded = DocumentVersion(
        document_id=document.id, version=0, status=DocumentStatus.SUPERSEDED, storage_path="/tmp/s.txt"
    )
    db.session.add_all([active, superseded])
    db.session.commit()

    valid_ids = TemporalResolver().get_valid_document_version_ids()

    assert valid_ids == {active.id}


def test_selects_version_valid_at_given_date(app_context):
    document = _make_document()
    now = datetime.now(timezone.utc)
    old = DocumentVersion(
        document_id=document.id,
        version=1,
        status=DocumentStatus.SUPERSEDED,
        storage_path="/tmp/old.txt",
        valid_from=now - timedelta(days=30),
        valid_to=now - timedelta(days=1),
    )
    current = DocumentVersion(
        document_id=document.id,
        version=2,
        status=DocumentStatus.ACTIVE,
        storage_path="/tmp/current.txt",
        valid_from=now - timedelta(days=1),
        valid_to=None,
    )
    db.session.add_all([old, current])
    db.session.commit()

    valid_now = TemporalResolver().get_valid_document_version_ids(as_of=now)
    valid_last_week = TemporalResolver().get_valid_document_version_ids(
        as_of=now - timedelta(days=10)
    )

    assert valid_now == {current.id}
    assert valid_last_week == {old.id}


def test_no_version_valid_at_a_date_before_document_existed(app_context):
    document = _make_document()
    now = datetime.now(timezone.utc)
    version = DocumentVersion(
        document_id=document.id,
        version=1,
        status=DocumentStatus.ACTIVE,
        storage_path="/tmp/v.txt",
        valid_from=now,
        valid_to=None,
    )
    db.session.add(version)
    db.session.commit()

    valid_ids = TemporalResolver().get_valid_document_version_ids(as_of=now - timedelta(days=365))

    assert valid_ids == set()


def test_overlapping_temporal_versions_picks_most_recent_valid_from(app_context):
    """Cas anormal (chevauchement de fenêtres temporelles) : on choisit la version
    dont le valid_from est le plus récent plutôt que de planter ou d'en renvoyer
    plusieurs pour un même document."""
    document = _make_document()
    now = datetime.now(timezone.utc)
    v1 = DocumentVersion(
        document_id=document.id,
        version=1,
        status=DocumentStatus.ACTIVE,
        storage_path="/tmp/v1.txt",
        valid_from=now - timedelta(days=10),
        valid_to=None,
    )
    v2 = DocumentVersion(
        document_id=document.id,
        version=2,
        status=DocumentStatus.ACTIVE,
        storage_path="/tmp/v2.txt",
        valid_from=now - timedelta(days=5),
        valid_to=None,
    )
    db.session.add_all([v1, v2])
    db.session.commit()

    valid_ids = TemporalResolver().get_valid_document_version_ids(as_of=now)

    assert valid_ids == {v2.id}
