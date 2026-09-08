"""
Blueprint `ingestion` — route HTTP pure (§9 : les routes Flask ne doivent pas
contenir la logique métier). Le fichier uploadé est mis en quarantaine dès
réception (jamais écrit directement dans le stockage définitif) ; toute
l'orchestration validation/parse/chunk/persistance vit dans `IngestionService`.
"""
from functools import wraps

from flask import Blueprint, request, jsonify, current_app, g

from app.modules.ingestion.service import IngestionService
from app.modules.ingestion.validation import FileValidationError
from app.modules.ingestion.quarantine import QuarantineManager
from app.extensions import db
from app.models.document import Permission
from app.modules.identity.decorators import require_auth

ingestion_bp = Blueprint("ingestion", __name__)


def _error_response(message: str, status_code: int):
    return (
        jsonify({"success": False, "data": None, "message": None, "error": message}),
        status_code,
    )


def _parse_optional_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _require_auth_unless_testing(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if current_app.testing:
            return view_func(*args, **kwargs)
        return require_auth(view_func)(*args, **kwargs)

    return wrapper
@ingestion_bp.post("")
@_require_auth_unless_testing
def ingest_document():
    if "file" not in request.files:
        return _error_response("Aucun fichier fourni (champ multipart 'file' attendu).", 400)

    upload = request.files["file"]
    if not upload.filename:
        return _error_response("Nom de fichier vide.", 400)

    title = request.form.get("title")
    if not title:
        return _error_response("Le champ 'title' est obligatoire.", 400)

    department_id = _parse_optional_int(request.form.get("department_id"))
    owner_id = g.current_user.id if getattr(g, "current_user", None) else None
    source = request.form.get("source", "chat")
    if source == "enterprise":
        if not g.current_user.role or g.current_user.role.name not in current_app.config["ADMIN_ROLE_NAMES"]:
            return _error_response("Seul un administrateur peut ajouter un document au corpus entreprise.", 403)
        if department_id is None:
            return _error_response("Le département est obligatoire pour le corpus entreprise.", 400)
    document_id = _parse_optional_int(request.form.get("document_id"))
    supersedes_version_id = _parse_optional_int(request.form.get("supersedes_version_id"))
    classification = request.form.get("classification")

    quarantine = QuarantineManager(current_app.config["QUARANTINE_DIR"])
    # Le fichier n'atteint jamais le stockage définitif directement : il est écrit
    # en quarantaine, et c'est IngestionService.ingest() qui décide de le libérer
    # (si validé) ou de le rejeter avec motif tracé (si non conforme).
    quarantine_path = quarantine.stage(upload, upload.filename)

    try:
        service = IngestionService(
            storage_dir=current_app.config["INGESTION_STORAGE_DIR"],
            quarantine_dir=current_app.config["QUARANTINE_DIR"],
            max_upload_size_mb=current_app.config["MAX_UPLOAD_SIZE_MB"],
            quarantine_manager=quarantine,
        )
        result = service.ingest(
            quarantine_file_path=quarantine_path,
            original_filename=upload.filename,
            title=title,
            department_id=department_id,
            classification=classification,
            owner_id=owner_id,
            document_id=document_id,
            supersedes_version_id=supersedes_version_id,
        )
        # Un upload utilisateur reste privé par défaut, mais son auteur peut
        # immédiatement l'utiliser comme contexte du chat.
        if getattr(g, "current_user", None):
            permission = Permission(
                document_id=result.document_id,
                document_version_id=result.document_version_id,
                allowed_roles=[],
                allowed_users=[g.current_user.id],
                allowed_departments=[],
            )
            db.session.add(permission)
            db.session.commit()
    except FileValidationError as e:
        return _error_response(str(e), 400)
    except ValueError as e:
        return _error_response(str(e), 400)

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "document_id": result.document_id,
                    "document_version_id": result.document_version_id,
                    "version_number": result.version_number,
                    "num_chunks": result.num_chunks,
                    "checksum": result.checksum,
                },
                "message": "Document ingéré avec succès.",
                "error": None,
            }
        ),
        201,
    )

