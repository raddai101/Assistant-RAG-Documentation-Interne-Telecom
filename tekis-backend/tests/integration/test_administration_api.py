import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.document import Permission
from app.models.identity import Role, User


@pytest.fixture
def app():
    flask_app = create_app("testing")
    with flask_app.app_context():
        db.create_all()
        admin_role = Role(name="admin")
        db.session.add(admin_role)
        db.session.flush()
        db.session.add(
            User(
                name="Admin",
                email="admin@test.local",
                password_hash=generate_password_hash("admin-password"),
                role=admin_role,
                active=True,
            )
        )
        db.session.commit()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def admin_headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "admin-password"},
    )
    return {"Authorization": f"Bearer {response.get_json()['data']['access_token']}"}


def test_role_crud_requires_admin_and_supports_lifecycle(client):
    response = client.get("/api/v1/admin/roles")
    assert response.status_code == 401

    headers = admin_headers(client)
    created = client.post(
        "/api/v1/admin/roles",
        json={"name": "reseau", "description": "Accès réseau"},
        headers=headers,
    )
    assert created.status_code == 201
    role_id = created.get_json()["data"]["role"]["id"]

    updated = client.patch(
        f"/api/v1/admin/roles/{role_id}",
        json={"description": "Accès réseau modifié"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["role"]["description"] == "Accès réseau modifié"

    deleted = client.delete(f"/api/v1/admin/roles/{role_id}", headers=headers)
    assert deleted.status_code == 200


def test_permission_crud_supports_lifecycle(client, app):
    headers = admin_headers(client)
    with app.app_context():
        permission = Permission(
            document_id=None,
            document_version_id=12,
            allowed_roles=["admin"],
            allowed_users=[],
            allowed_departments=[],
        )
        db.session.add(permission)
        db.session.commit()
        permission_id = permission.id

    updated = client.patch(
        f"/api/v1/admin/permissions/{permission_id}",
        json={"allowed_roles": ["reseau"]},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["permission"]["allowed_roles"] == ["reseau"]

    deleted = client.delete(f"/api/v1/admin/permissions/{permission_id}", headers=headers)
    assert deleted.status_code == 200
