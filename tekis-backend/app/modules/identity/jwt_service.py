"""
Service JWT (module `identity`, Phase 5, memoire.md décision Auth = JWT + DB).

Le token ne porte que l'identité (`sub` = user id) et un horodatage d'expiration —
jamais le rôle ou le département en clair dans le payload : ces attributs sont
toujours relus depuis la base au moment de la requête (`decorators.require_auth`),
pour que toute modification de rôle/département par un administrateur soit
immédiatement effective sans attendre l'expiration d'un token déjà émis.
"""
from datetime import datetime, timedelta, timezone

import jwt

from app.models.identity import User


class JWTError(ValueError):
    """Levée quand un token est absent, invalide, mal signé ou expiré."""


class JWTService:
    def __init__(self, secret_key: str, expires_minutes: int = 60, algorithm: str = "HS256"):
        self._secret_key = secret_key
        self._expires_minutes = expires_minutes
        self._algorithm = algorithm

    def encode(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "iat": now,
            "exp": now + timedelta(minutes=self._expires_minutes),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError as e:
            raise JWTError("Token expiré.") from e
        except jwt.InvalidTokenError as e:
            raise JWTError("Token invalide.") from e
