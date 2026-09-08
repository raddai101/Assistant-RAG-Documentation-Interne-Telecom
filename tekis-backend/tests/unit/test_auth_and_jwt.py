import time

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models.identity import User, Role
from app.modules.identity.service import AuthService
from app.modules.identity.jwt_service import JWTService, JWTError


@pytest.fixture
def app_context():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _make_user(email="alice@tekis.local", password="correct-horse", active=True, role_name=None):
    role = None
    if role_name:
        role = Role(name=role_name)
        db.session.add(role)
        db.session.flush()
    user = User(
        name="Alice",
        email=email,
        password_hash=generate_password_hash(password),
        active=active,
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_authenticate_succeeds_with_correct_credentials(app_context):
    _make_user(email="alice@tekis.local", password="correct-horse")

    user = AuthService().authenticate("alice@tekis.local", "correct-horse")

    assert user is not None
    assert user.email == "alice@tekis.local"


def test_authenticate_fails_with_wrong_password(app_context):
    _make_user(email="alice@tekis.local", password="correct-horse")

    user = AuthService().authenticate("alice@tekis.local", "wrong-password")

    assert user is None


def test_authenticate_fails_for_unknown_email(app_context):
    user = AuthService().authenticate("inconnu@tekis.local", "peu-importe")
    assert user is None


def test_authenticate_fails_for_inactive_user(app_context):
    _make_user(email="alice@tekis.local", password="correct-horse", active=False)

    user = AuthService().authenticate("alice@tekis.local", "correct-horse")

    assert user is None


def test_jwt_encode_decode_roundtrip(app_context):
    user = _make_user()
    service = JWTService(secret_key="test-secret", expires_minutes=60)

    token = service.encode(user)
    payload = service.decode(token)

    assert payload["sub"] == str(user.id)


def test_jwt_decode_rejects_tampered_token(app_context):
    user = _make_user()
    service = JWTService(secret_key="test-secret", expires_minutes=60)
    token = service.encode(user)

    with pytest.raises(JWTError):
        JWTService(secret_key="wrong-secret", expires_minutes=60).decode(token)


def test_jwt_decode_rejects_expired_token(app_context):
    user = _make_user()
    service = JWTService(secret_key="test-secret", expires_minutes=0)
    token = service.encode(user)
    time.sleep(1.1)

    with pytest.raises(JWTError, match="expiré"):
        service.decode(token)
