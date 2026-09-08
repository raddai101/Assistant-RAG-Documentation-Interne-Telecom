"""
Blueprint `graph` — CRUD/navigation du Knowledge Graph (Phase 4, memoire.md §10).
Routes HTTP pures (§9) : toute la logique vit dans `GraphService`.
"""
from flask import Blueprint, request, jsonify, current_app

from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService, EntityNotFoundError

graph_bp = Blueprint("graph", __name__)


def _build_graph_service(app_config) -> GraphService:
    graph_store = Neo4jGraphStore(
        uri=app_config["NEO4J_URI"],
        user=app_config["NEO4J_USER"],
        password=app_config["NEO4J_PASSWORD"],
    )
    return GraphService(graph_store)


def _error_response(message: str, status_code: int):
    return (
        jsonify({"success": False, "data": None, "message": None, "error": message}),
        status_code,
    )


def _entity_to_dict(entity: GraphEntity) -> dict:
    return {
        "id": entity.id,
        "type": entity.type,
        "name": entity.name,
        "properties": entity.properties,
        "source_chunk_ids": entity.source_chunk_ids,
    }


@graph_bp.post("/entities")
def upsert_entity():
    payload = request.get_json(silent=True) or {}
    for required_field in ("id", "type", "name"):
        if not payload.get(required_field):
            return _error_response(f"Le champ '{required_field}' est obligatoire.", 400)

    entity = GraphEntity(
        id=payload["id"],
        type=payload["type"],
        name=payload["name"],
        properties=payload.get("properties", {}),
        source_chunk_ids=payload.get("source_chunk_ids", []),
    )

    service = _build_graph_service(current_app.config)
    service.upsert_entity(entity)

    return jsonify({"success": True, "data": _entity_to_dict(entity), "message": None, "error": None}), 201


@graph_bp.get("/entities/<entity_id>")
def get_entity(entity_id: str):
    service = _build_graph_service(current_app.config)
    entity = service.get_entity(entity_id)

    if entity is None:
        return _error_response(f"Entité '{entity_id}' introuvable.", 404)

    return jsonify({"success": True, "data": _entity_to_dict(entity), "message": None, "error": None})


@graph_bp.delete("/entities/<entity_id>")
def delete_entity(entity_id: str):
    service = _build_graph_service(current_app.config)

    if service.get_entity(entity_id) is None:
        return _error_response(f"Entité '{entity_id}' introuvable.", 404)

    service.delete_entity(entity_id)
    return jsonify({"success": True, "data": {"deleted": True}, "message": None, "error": None})


@graph_bp.get("/entities/<entity_id>/related")
def get_related_entities(entity_id: str):
    relationship_type = request.args.get("type")
    depth = request.args.get("depth", default=1, type=int)

    service = _build_graph_service(current_app.config)

    if service.get_entity(entity_id) is None:
        return _error_response(f"Entité '{entity_id}' introuvable.", 404)

    try:
        related = service.get_related_entities(entity_id, relationship_type=relationship_type, depth=depth)
    except ValueError as e:
        return _error_response(str(e), 400)

    return jsonify(
        {
            "success": True,
            "data": {"results": [_entity_to_dict(e) for e in related]},
            "message": None,
            "error": None,
        }
    )


@graph_bp.post("/relationships")
def upsert_relationship():
    payload = request.get_json(silent=True) or {}
    for required_field in ("source_id", "target_id", "type"):
        if not payload.get(required_field):
            return _error_response(f"Le champ '{required_field}' est obligatoire.", 400)

    relationship = GraphRelationship(
        source_id=payload["source_id"],
        target_id=payload["target_id"],
        type=payload["type"],
        properties=payload.get("properties", {}),
        source_chunk_ids=payload.get("source_chunk_ids", []),
    )

    service = _build_graph_service(current_app.config)

    try:
        service.upsert_relationship(relationship)
    except EntityNotFoundError as e:
        return _error_response(str(e), 400)
    except ValueError as e:
        return _error_response(str(e), 400)

    return (
        jsonify(
            {
                "success": True,
                "data": {
                    "source_id": relationship.source_id,
                    "target_id": relationship.target_id,
                    "type": relationship.type,
                    "properties": relationship.properties,
                    "source_chunk_ids": relationship.source_chunk_ids,
                },
                "message": None,
                "error": None,
            }
        ),
        201,
    )
