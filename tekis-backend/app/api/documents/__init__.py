"""Routes de lecture sécurisée des documents et de leurs aperçus."""
from flask import Blueprint, jsonify, current_app, g

from app.extensions import db
from app.models.document import Document, DocumentVersion
from app.modules.documents.preview_service import DocumentPreviewError, DocumentPreviewService
from app.modules.governance.access_control_service import AccessControlService
from app.modules.governance.temporal_resolver import TemporalResolver
from app.modules.identity.decorators import require_auth

documents_bp = Blueprint("documents", __name__)


def _can_access_version(version_id: int) -> bool:
    authorized_ids = AccessControlService(
        admin_role_names=current_app.config["ADMIN_ROLE_NAMES"]
    ).get_authorized_document_version_ids(g.current_user)
    if authorized_ids is not None and version_id not in authorized_ids:
        return False

    valid_ids = TemporalResolver().get_valid_document_version_ids()
    return version_id in valid_ids


@documents_bp.get("/<int:document_id>")
@require_auth
def get_document(document_id: int):
    document = db.session.get(Document, document_id)
    if document is None:
        return jsonify({"success": False, "data": None, "message": None, "error": "Document introuvable."}), 404

    return jsonify({
        "success": True,
        "data": {
            "id": document.id,
            "title": document.title,
            "department_id": document.department_id,
            "department_name": document.department.name if document.department else None,
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
    })


@documents_bp.get("/versions/<int:version_id>/preview")
@require_auth
def preview_document(version_id: int):
    version = db.session.get(DocumentVersion, version_id)
    if version is None:
        return jsonify({"success": False, "data": None, "message": None, "error": "Version du document introuvable."}), 404

    if not _can_access_version(version_id):
        return jsonify({"success": False, "data": None, "message": None, "error": "Accès au document non autorisé."}), 403

    try:
        data = DocumentPreviewService().preview(version)
    except DocumentPreviewError as exc:
        return jsonify({"success": False, "data": None, "message": None, "error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"success": False, "data": None, "message": None, "error": f"Impossible de prévisualiser le document : {exc}"}), 422

    return jsonify({"success": True, "data": data, "message": None, "error": None})
