"""Routes d'administration des utilisateurs, rôles et permissions ACL."""
from functools import wraps

from flask import Blueprint, g, jsonify, request
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.document import Permission
from app.models.identity import Department, Role, User
from app.modules.identity.decorators import require_auth


administration_bp = Blueprint("administration", __name__)


def _admin_only(view_func):
    @wraps(view_func)
    @require_auth
    def wrapper(*args, **kwargs):
        user = g.current_user
        if user.role is None or user.role.name != "admin":
            return _response("Accès administrateur requis.", 403)
        return view_func(*args, **kwargs)

    return wrapper


def _response(error=None, status=200, data=None, message=None):
    return jsonify({"success": error is None, "data": data, "message": message, "error": error}), status


def _role_data(role):
    return {"id": role.id, "name": role.name, "description": role.description}


def _user_data(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "active": user.active,
        "department_id": user.department_id,
        "role": _role_data(user.role) if user.role else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _permission_data(permission):
    return {
        "id": permission.id,
        "document_id": permission.document_id,
        "document_version_id": permission.document_version_id,
        "allowed_roles": permission.allowed_roles or [],
        "allowed_users": permission.allowed_users or [],
        "allowed_departments": permission.allowed_departments or [],
    }


@administration_bp.get("/users")
@_admin_only
def list_users():
    return _response(data={"users": [_user_data(user) for user in User.query.order_by(User.id).all()]})


@administration_bp.post("/users")
@_admin_only
def create_user():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    email = str(body.get("email", "")).strip().lower()
    password = body.get("password")
    if not name or not email or not password:
        return _response("Les champs 'name', 'email' et 'password' sont obligatoires.", 400)
    if User.query.filter_by(email=email).first():
        return _response("Cette adresse email existe déjà.", 409)

    role = None
    if body.get("role_id") is not None:
        role = db.session.get(Role, body["role_id"])
        if role is None:
            return _response("Rôle introuvable.", 404)
    user = User(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        department_id=body.get("department_id"),
        active=bool(body.get("active", True)),
    )
    db.session.add(user)
    db.session.commit()
    return _response(data={"user": _user_data(user)}, status=201, message="Utilisateur créé.")


@administration_bp.patch("/users/<int:user_id>")
@_admin_only
def update_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return _response("Utilisateur introuvable.", 404)
    body = request.get_json(silent=True) or {}
    if "name" in body:
        user.name = str(body["name"]).strip()
    if "email" in body:
        email = str(body["email"]).strip().lower()
        duplicate = User.query.filter(User.email == email, User.id != user.id).first()
        if duplicate:
            return _response("Cette adresse email existe déjà.", 409)
        user.email = email
    if "password" in body and body["password"]:
        user.password_hash = generate_password_hash(body["password"])
    if "role_id" in body:
        user.role = db.session.get(Role, body["role_id"]) if body["role_id"] is not None else None
        if body["role_id"] is not None and user.role is None:
            return _response("Rôle introuvable.", 404)
    if "department_id" in body:
        user.department_id = body["department_id"]
    if "active" in body:
        user.active = bool(body["active"])
    db.session.commit()
    return _response(data={"user": _user_data(user)}, message="Utilisateur modifié.")


@administration_bp.delete("/users/<int:user_id>")
@_admin_only
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return _response("Utilisateur introuvable.", 404)
    if user.id == g.current_user.id:
        return _response("Vous ne pouvez pas supprimer votre propre compte.", 400)
    db.session.delete(user)
    db.session.commit()
    return _response(message="Utilisateur supprimé.")


@administration_bp.get("/roles")
@_admin_only
def list_roles():
    return _response(data={"roles": [_role_data(role) for role in Role.query.order_by(Role.id).all()]})


@administration_bp.get("/departments")
@_admin_only
def list_departments():
    return _response(data={"departments": [{"id": d.id, "name": d.name} for d in Department.query.order_by(Department.name).all()]})


@administration_bp.post("/roles")
@_admin_only
def create_role():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return _response("Le champ 'name' est obligatoire.", 400)
    if Role.query.filter_by(name=name).first():
        return _response("Ce rôle existe déjà.", 409)
    role = Role(name=name, description=body.get("description"))
    db.session.add(role)
    db.session.commit()
    return _response(data={"role": _role_data(role)}, status=201, message="Rôle créé.")


@administration_bp.patch("/roles/<int:role_id>")
@_admin_only
def update_role(role_id):
    role = db.session.get(Role, role_id)
    if role is None:
        return _response("Rôle introuvable.", 404)
    body = request.get_json(silent=True) or {}
    if "name" in body:
        name = str(body["name"]).strip()
        duplicate = Role.query.filter(Role.name == name, Role.id != role.id).first()
        if duplicate:
            return _response("Ce rôle existe déjà.", 409)
        role.name = name
    if "description" in body:
        role.description = body["description"]
    db.session.commit()
    return _response(data={"role": _role_data(role)}, message="Rôle modifié.")


@administration_bp.delete("/roles/<int:role_id>")
@_admin_only
def delete_role(role_id):
    role = db.session.get(Role, role_id)
    if role is None:
        return _response("Rôle introuvable.", 404)
    if role.name == "admin":
        return _response("Le rôle admin est protégé.", 400)
    if User.query.filter_by(role_id=role.id).first():
        return _response("Ce rôle est encore attribué à un utilisateur.", 409)
    db.session.delete(role)
    db.session.commit()
    return _response(message="Rôle supprimé.")


@administration_bp.get("/permissions")
@_admin_only
def list_permissions():
    permissions = Permission.query.order_by(Permission.id).all()
    return _response(data={"permissions": [_permission_data(permission) for permission in permissions]})


@administration_bp.post("/permissions")
@_admin_only
def create_permission():
    body = request.get_json(silent=True) or {}
    if body.get("document_id") is None and body.get("document_version_id") is None:
        return _response("document_id ou document_version_id est obligatoire.", 400)
    permission = Permission(
        document_id=body.get("document_id"),
        document_version_id=body.get("document_version_id"),
        allowed_roles=body.get("allowed_roles", []),
        allowed_users=body.get("allowed_users", []),
        allowed_departments=body.get("allowed_departments", []),
    )
    db.session.add(permission)
    db.session.commit()
    return _response(data={"permission": _permission_data(permission)}, status=201, message="ACL créée.")


@administration_bp.patch("/permissions/<int:permission_id>")
@_admin_only
def update_permission(permission_id):
    permission = db.session.get(Permission, permission_id)
    if permission is None:
        return _response("ACL introuvable.", 404)
    body = request.get_json(silent=True) or {}
    for field in ("document_id", "document_version_id", "allowed_roles", "allowed_users", "allowed_departments"):
        if field in body:
            setattr(permission, field, body[field])
    db.session.commit()
    return _response(data={"permission": _permission_data(permission)}, message="ACL modifiée.")


@administration_bp.delete("/permissions/<int:permission_id>")
@_admin_only
def delete_permission(permission_id):
    permission = db.session.get(Permission, permission_id)
    if permission is None:
        return _response("ACL introuvable.", 404)
    db.session.delete(permission)
    db.session.commit()
    return _response(message="ACL supprimée.")