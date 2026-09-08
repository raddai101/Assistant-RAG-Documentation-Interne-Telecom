import pytest

from app import create_app
from app.extensions import db
from app.models.identity import User, Role, Department
from app.models.document import Document, DocumentVersion, Permission, DocumentStatus
from app.modules.governance.access_control_service import AccessControlService
from app.modules.governance.repository import GovernanceRepository


@pytest.fixture
def app_context():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _make_document_version(document_id_suffix=""):
    document = Document(title=f"Doc {document_id_suffix}")
    db.session.add(document)
    db.session.flush()
    version = DocumentVersion(
        document_id=document.id,
        version=1,
        status=DocumentStatus.ACTIVE,
        storage_path="/tmp/fake.txt",
    )
    db.session.add(version)
    db.session.commit()
    return document, version


def _make_user(role_name=None, department_name=None):
    role = None
    department = None
    if role_name:
        role = Role(name=role_name)
        db.session.add(role)
    if department_name:
        department = Department(name=department_name)
        db.session.add(department)
    db.session.flush()
    user = User(
        name="Test User",
        email=f"{role_name or 'user'}-{department_name or 'x'}@tekis.local",
        password_hash="irrelevant",
        role=role,
        department=department,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_document_without_any_permission_is_denied_by_default(app_context):
    _, version = _make_document_version()
    user = _make_user(role_name="employe")

    authorized = AccessControlService().get_authorized_document_version_ids(user)

    assert authorized == set()  # default-deny


def test_admin_role_bypasses_all_restrictions(app_context):
    _make_document_version()
    admin = _make_user(role_name="admin")

    authorized = AccessControlService().get_authorized_document_version_ids(admin)

    assert authorized is None  # None = accès illimité, jamais confondu avec vide


def test_permission_by_role_grants_access(app_context):
    document, version = _make_document_version()
    db.session.add(
        Permission(document_id=document.id, allowed_roles=["reseau"], allowed_users=[], allowed_departments=[])
    )
    db.session.commit()
    user = _make_user(role_name="reseau")

    authorized = AccessControlService().get_authorized_document_version_ids(user)

    assert authorized == {version.id}


def test_permission_by_role_denies_other_role(app_context):
    document, version = _make_document_version()
    db.session.add(
        Permission(document_id=document.id, allowed_roles=["reseau"], allowed_users=[], allowed_departments=[])
    )
    db.session.commit()
    other_user = _make_user(role_name="rh")

    authorized = AccessControlService().get_authorized_document_version_ids(other_user)

    assert authorized == set()


def test_permission_by_department_grants_access(app_context):
    document, version = _make_document_version()
    department = Department(name="Réseau")
    db.session.add(department)
    db.session.flush()
    db.session.add(
        Permission(
            document_id=document.id, allowed_roles=[], allowed_users=[], allowed_departments=[department.id]
        )
    )
    db.session.commit()
    user = User(
        name="Bob",
        email="bob@tekis.local",
        password_hash="irrelevant",
        department_id=department.id,
    )
    db.session.add(user)
    db.session.commit()

    authorized = AccessControlService().get_authorized_document_version_ids(user)

    assert authorized == {version.id}


def test_permission_by_nominative_user_grants_access(app_context):
    document, version = _make_document_version()
    user = _make_user()
    db.session.add(
        Permission(document_id=document.id, allowed_roles=[], allowed_users=[user.id], allowed_departments=[])
    )
    db.session.commit()

    authorized = AccessControlService().get_authorized_document_version_ids(user)

    assert authorized == {version.id}


def test_version_level_permission_does_not_leak_to_other_versions(app_context):
    document, version = _make_document_version()
    version2 = DocumentVersion(
        document_id=document.id, version=2, status=DocumentStatus.ACTIVE, storage_path="/tmp/v2.txt"
    )
    db.session.add(version2)
    db.session.flush()
    db.session.add(
        Permission(
            document_version_id=version.id, allowed_roles=["reseau"], allowed_users=[], allowed_departments=[]
        )
    )
    db.session.commit()
    user = _make_user(role_name="reseau")

    authorized = AccessControlService().get_authorized_document_version_ids(user)

    assert authorized == {version.id}
    assert version2.id not in authorized
