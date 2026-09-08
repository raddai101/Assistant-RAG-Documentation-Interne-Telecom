"""
Blueprint `search` — `POST /api/v1/search` : retrieval brut, sans génération, utile
pour debug/éval (memoire.md §7). Route HTTP pure (§9).

Depuis la Phase 3, utilise `HybridRetrievalService` (fusion lexicale PostgreSQL FTS +
vectorielle ChromaDB + reranking cross-encoder) au lieu du `RetrievalService`
purement vectoriel de la Phase 2 — le contrat HTTP de cette route est inchangé
(même requête, même forme de réponse), seule l'implémentation change (§3.1).

Depuis la Phase 5, protégée par `require_auth` (§15 : IDENTITÉ -> Rôle/ACL ->
Retrieval autorisé -> ...). L'intersection ACL (`AccessControlService`) et
temporelle (`TemporalResolver`) est calculée AVANT tout appel au retrieval, jamais
après — un document interdit ou temporellement invalide n'atteint jamais le
vector store ni le moteur lexical.
"""
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app, g

from app.modules.generation.ollama_client import OllamaEmbeddingClient, OllamaError
from app.modules.retrieval.vector.chroma_store import ChromaVectorStore
from app.modules.retrieval.lexical.postgres_fts import PostgresFtsLexicalSearch
from app.modules.retrieval.reranker.cross_encoder import CrossEncoderReranker
from app.modules.retrieval.hybrid_service import HybridRetrievalService
from app.modules.identity.decorators import require_auth
from app.modules.governance.access_control_service import AccessControlService
from app.modules.governance.temporal_resolver import TemporalResolver

search_bp = Blueprint("search", __name__)


def _build_retrieval_service(app_config) -> HybridRetrievalService:
    embedding_client = OllamaEmbeddingClient(
        base_url=app_config["OLLAMA_BASE_URL"],
        model=app_config["OLLAMA_EMBEDDING_MODEL"],
    )
    vector_store = ChromaVectorStore(
        persist_dir=app_config["CHROMA_PERSIST_DIR"],
        collection_name=app_config["CHROMA_COLLECTION_NAME"],
    )
    return HybridRetrievalService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        lexical_search=PostgresFtsLexicalSearch(),
        reranker=CrossEncoderReranker(model_name=app_config["RERANKER_MODEL_NAME"]),
        default_top_k=app_config.get("RETRIEVAL_TOP_K", 5),
        candidate_k=app_config.get("HYBRID_CANDIDATE_K", 20),
    )


def _resolve_authorized_version_ids(user, as_of: datetime | None) -> set[int] | None:
    """Intersection ACL x temporel (§12, §15, §16). `None` = pas de restriction
    (rôle admin) ; sinon intersection explicite des deux ensembles autorisés."""
    acl_ids = AccessControlService(
        admin_role_names=current_app.config["ADMIN_ROLE_NAMES"]
    ).get_authorized_document_version_ids(user)
    temporal_ids = TemporalResolver().get_valid_document_version_ids(as_of=as_of)
    if acl_ids is None:  # admin : pas de restriction ACL, seule la temporalité s'applique
        return temporal_ids
    return acl_ids & temporal_ids


def _parse_as_of(body: dict) -> datetime | None:
    raw = body.get("as_of")
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@search_bp.post("")
@require_auth
def search():
    body = request.get_json(silent=True) or {}
    query = body.get("query")
    if not query:
        return (
            jsonify(
                {"success": False, "data": None, "message": None, "error": "Le champ 'query' est obligatoire."}
            ),
            400,
        )
    top_k = body.get("top_k")
    as_of = _parse_as_of(body)

    authorized_ids = _resolve_authorized_version_ids(g.current_user, as_of)

    service = _build_retrieval_service(current_app.config)
    try:
        result = service.search(query, top_k=top_k, authorized_document_version_ids=authorized_ids)
    except OllamaError as e:
        return (
            jsonify({"success": False, "data": None, "message": None, "error": str(e)}),
            503,
        )

    return jsonify(
        {
            "success": True,
            "data": {
                "results": [
                    {
                        "chunk_id": r.metadata.get("chunk_id"),
                        "document_version_id": r.metadata.get("document_version_id"),
                        "page": r.metadata.get("page"),
                        "content": r.document,
                        "distance": r.distance,
                    }
                    for r in result.results
                ]
            },
            "message": None,
            "error": None,
        }
    )
