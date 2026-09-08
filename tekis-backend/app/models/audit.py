"""
Modèles de gouvernance (module `governance`) : AuditLog, Session, Feedback.

Statut : structure créée en Phase 1 pour stabiliser le schéma relationnel global,
mais aucune logique d'écriture d'audit ni de gestion de session n'est implémentée
avant les phases concernées (Sécurité/ACL = Phase 5, Validation = Phase 6).
"""
from datetime import datetime, timezone

from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    action = db.Column(db.String(100), nullable=False)
    accessed_resources = db.Column(db.JSON, default=list)
    response_id = db.Column(db.String(100), nullable=True)
    authorized = db.Column(db.Boolean, nullable=True)

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_id}>"


class Session(db.Model):
    __tablename__ = "sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Session user={self.user_id}>"


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    response_id = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Feedback response={self.response_id} rating={self.rating}>"
