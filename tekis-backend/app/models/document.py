"""
Modèles documentaires (module `knowledge`) : Document, DocumentVersion, Permission.

Cœur du schéma de la Phase 1 (Ingestion). Le versioning temporel (valid_from,
valid_to, supersedes, status) est modélisé dès maintenant car il structure la table,
mais la logique de résolution temporelle automatique (choisir la bonne version selon
une date) reste non implémentée avant la Phase 5 (memoire.md §11).
"""
from datetime import datetime, timezone
import enum

from app.extensions import db


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    classification = db.Column(db.String(50), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    department = db.relationship("Department")
    owner = db.relationship("User")
    versions = db.relationship(
        "DocumentVersion", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Document {self.id} {self.title!r}>"


class DocumentVersion(db.Model):
    __tablename__ = "document_versions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    valid_from = db.Column(db.DateTime, nullable=True)
    valid_to = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.Enum(DocumentStatus), default=DocumentStatus.DRAFT, nullable=False
    )
    supersedes_version_id = db.Column(
        db.Integer, db.ForeignKey("document_versions.id"), nullable=True
    )
    storage_path = db.Column(db.String(500), nullable=False)
    checksum = db.Column(db.String(128), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(20), nullable=True)  # pdf, docx, xlsx, txt
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    document = db.relationship("Document", back_populates="versions")
    supersedes = db.relationship("DocumentVersion", remote_side=[id])
    chunks = db.relationship(
        "Chunk", back_populates="document_version", cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("document_id", "version", name="uq_document_version"),
    )

    def __repr__(self):
        return f"<DocumentVersion doc={self.document_id} v={self.version}>"


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)
    document_version_id = db.Column(
        db.Integer, db.ForeignKey("document_versions.id"), nullable=True
    )
    allowed_roles = db.Column(db.JSON, default=list)
    allowed_users = db.Column(db.JSON, default=list)
    allowed_departments = db.Column(db.JSON, default=list)

    def __repr__(self):
        return f"<Permission doc={self.document_id} version={self.document_version_id}>"
