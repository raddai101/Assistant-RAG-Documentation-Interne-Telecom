"""
Blueprint `change_intelligence` — `POST /api/v1/change-intelligence/compare`
(memoire.md §15). Route HTTP pure (§9) : toute la logique vit dans
`ChangeIntelligenceService`.
"""
from flask import Blueprint, request, jsonify, current_app

from app.modules.change_intelligence.repository import (
    ChangeIntelligenceRepository,
    DocumentVersionNotFoundError,
)
from app.modules.change_intelligence.service import ChangeIntelligenceService
from app.modules.change_intelligence.impact_service import ImpactAnalysisService
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService
from app.modules.change_intelligence.contracts import VersionComparisonResult, ImpactAnalysisResult

change_intelligence_bp = Blueprint("change_intelligence", __name__)


def _build_service(app_config) -> ChangeIntelligenceService:
    repository = ChangeIntelligenceRepository()

    # L'analyse d'impact est optionnelle (le Knowledge Graph complète, memoire.md
    # §10) : si Neo4j n'est pas configuré/accessible, le diff reste utilisable seul.
    impact_service = None
    try:
        graph_store = Neo4jGraphStore(
            uri=app_config["NEO4J_URI"],
            user=app_config["NEO4J_USER"],
            password=app_config["NEO4J_PASSWORD"],
        )
        impact_service = ImpactAnalysisService(GraphService(graph_store))
    except Exception:
        impact_service = None

    return ChangeIntelligenceService(repository=repository, impact_service=impact_service)


def _error_response(message: str, status_code: int):
    return (
        jsonify({"success": False, "data": None, "message": None, "error": message}),
        status_code,
    )


def _diff_to_dict(diff) -> dict:
    return {
        "change_type": diff.change_type.value,
        "chunk_id_from": diff.chunk_id_from,
        "chunk_id_to": diff.chunk_id_to,
        "content_from": diff.content_from,
        "content_to": diff.content_to,
        "similarity": diff.similarity,
    }


def _comparison_to_dict(comparison: VersionComparisonResult) -> dict:
    return {
        "document_id": comparison.document_id,
        "version_from": comparison.version_from,
        "version_to": comparison.version_to,
        "additions": [_diff_to_dict(d) for d in comparison.additions],
        "removals": [_diff_to_dict(d) for d in comparison.removals],
        "modifications": [_diff_to_dict(d) for d in comparison.modifications],
        "unchanged_count": comparison.unchanged_count,
    }


def _impact_to_dict(impact: ImpactAnalysisResult | None) -> dict | None:
    if impact is None:
        return None
    return {
        "directly_linked_entities": [
            {"entity_id": e.entity_id, "type": e.type, "name": e.name, "via_chunk_ids": e.via_chunk_ids}
            for e in impact.directly_linked_entities
        ],
        "indirectly_related_entities": [
            {"entity_id": e.entity_id, "type": e.type, "name": e.name}
            for e in impact.indirectly_related_entities
        ],
    }


@change_intelligence_bp.post("/compare")
def compare_versions():
    payload = request.get_json(silent=True) or {}
    document_id = payload.get("document_id")
    if not document_id:
        return _error_response("Le champ 'document_id' est obligatoire.", 400)

    version_from = payload.get("version_from")
    version_to = payload.get("version_to")
    include_impact = payload.get("include_impact", True)

    service = _build_service(current_app.config)

    try:
        comparison = service.compare_versions(document_id, version_from, version_to)
    except DocumentVersionNotFoundError as e:
        return _error_response(str(e), 404)

    impact = service.analyze_impact(comparison) if include_impact else None

    return jsonify(
        {
            "success": True,
            "data": {
                "comparison": _comparison_to_dict(comparison),
                "impact": _impact_to_dict(impact),
            },
            "message": None,
            "error": None,
        }
    )
