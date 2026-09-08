"""
Modèles d'identité organisationnelle (module `identity`).

Statut : structure de données créée en Phase 1 (nécessaire pour rattacher un document
à un département/propriétaire dès l'ingestion), mais la logique d'authentification
JWT et le filtrage ACL restent non implémentés avant la Phase 5, conformément à la
progression par phases (memoire.md §12, §21).
"""
from datetime import datetime, timezone

from app.extensions import db


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    parent = db.relationship("Department", remote_side=[id], backref="children")

    def __repr__(self):
        return f"<Department {self.name}>"


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Role {self.name}>"


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    department = db.relationship("Department")
    role = db.relationship("Role")

    def __repr__(self):
        return f"<User {self.email}>"
