"""
Blueprint `documents` — lecture seule pour l'instant (Phase 1). Pas de filtrage ACL :
non implémenté avant la Phase 5, conformément à la progression par phases.
"""
from flask import Blueprint, jsonify

from app.extensions import db
from app.models.document import Document

documents_bp = Blueprint("documents", __name__)


@documents_bp.get("/<int:document_id>")
def get_document(document_id: int):
    document = db.session.get(Document, document_id)
    if document is None:
        return (
            jsonify(
                {"success": False, "data": None, "message": None, "error": "Document introuvable."}
            ),
            404,
        )

    return jsonify(
        {
            "success": True,
            "data": {
                "id": document.id,
                "title": document.title,
                "department_id": document.department_id,
                "classification": document.classification,
                "versions": [
                    {
                        "id": v.id,
                        "version": v.version,
                        "status": v.status.value,
                        "file_type": v.file_type,
                        "original_filename": v.original_filename,
                        "num_chunks": len(v.chunks),
                    }
                    for v in document.versions
                ],
            },
            "message": None,
            "error": None,
        }
    )
