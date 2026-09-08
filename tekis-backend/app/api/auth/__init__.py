"""
Blueprint `auth` — `POST /api/v1/auth/login` (memoire.md §7, Phase 5). Route HTTP
pure (§9) : toute la logique vit dans `AuthService`/`JWTService`.
"""
from flask import Blueprint, request, jsonify, current_app

from app.modules.identity.service import AuthService
from app.modules.identity.jwt_service import JWTService

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    email = body.get("email")
    password = body.get("password")
    if not email or not password:
        return (
            jsonify(
                {
                    "success": False,
                    "data": None,
                    "message": None,
                    "error": "Les champs 'email' et 'password' sont obligatoires.",
                }
            ),
            400,
        )

    user = AuthService().authenticate(email, password)
    if user is None:
        return (
            jsonify(
                {"success": False, "data": None, "message": None, "error": "Identifiants invalides."}
            ),
            401,
        )

    jwt_service = JWTService(
        secret_key=current_app.config["JWT_SECRET_KEY"],
        expires_minutes=current_app.config["JWT_ACCESS_TOKEN_EXPIRES_MINUTES"],
    )
    token = jwt_service.encode(user)

    return jsonify(
        {
            "success": True,
            "data": {
                "access_token": token,
                "expires_in_minutes": current_app.config["JWT_ACCESS_TOKEN_EXPIRES_MINUTES"],
                "user": {
                    "id": user.id,
                    "name": user.name,
                    "email": user.email,
                    "role": user.role.name if user.role else None,
                    "department_id": user.department_id,
                },
            },
            "message": None,
            "error": None,
        }
    )
