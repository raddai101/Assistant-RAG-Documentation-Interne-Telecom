"""
Service d'authentification (module `identity`, Phase 5). Vérifie les identifiants et
renvoie l'utilisateur correspondant — ne gère ni la génération de token (voir
`jwt_service.py`) ni le filtrage ACL (module `governance`), pour rester conforme à
la séparation des responsabilités (§9 des instructions).
"""
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.identity import User


class AuthService:
    def authenticate(self, email: str, password: str) -> User | None:
        user = db.session.query(User).filter_by(email=email).first()
        if user is None or not user.active:
            return None
        if not check_password_hash(user.password_hash, password):
            return None
        return user
