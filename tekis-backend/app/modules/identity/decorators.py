"""
Décorateur `require_auth` (module `identity`, Phase 5).

Applique le premier maillon du pipeline de sécurité obligatoire (§15 des
instructions : IDENTITÉ -> Rôle/ACL -> Retrieval autorisé -> Contexte autorisé ->
LLM). Sans identité vérifiée, aucune route protégée ne s'exécute — la vérification a
lieu ici, jamais plus loin dans le pipeline.
"""
from functools import wraps

from flask import request, jsonify, current_app, g

from app.extensions import db
from app.models.identity import User
from app.modules.identity.jwt_service import JWTService, JWTError


def require_auth(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _unauthorized("En-tête 'Authorization: Bearer <token>' manquant.")

        token = auth_header[len("Bearer "):].strip()
        jwt_service = JWTService(
            secret_key=current_app.config["JWT_SECRET_KEY"],
            expires_minutes=current_app.config["JWT_ACCESS_TOKEN_EXPIRES_MINUTES"],
        )
        try:
            payload = jwt_service.decode(token)
        except JWTError as e:
            return _unauthorized(str(e))

        # Rôle/département toujours relus depuis la base (pas depuis le token) pour
        # qu'une modification d'habilitation soit immédiatement effective.
        user = db.session.get(User, int(payload["sub"]))
        if user is None or not user.active:
            return _unauthorized("Utilisateur introuvable ou désactivé.")

        g.current_user = user
        return view_func(*args, **kwargs)

    return wrapper


def _unauthorized(message: str):
    return (
        jsonify({"success": False, "data": None, "message": None, "error": message}),
        401,
    )
