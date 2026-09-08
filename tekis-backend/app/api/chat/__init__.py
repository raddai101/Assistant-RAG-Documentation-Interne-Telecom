"""
Blueprint `chat` — `POST /api/v1/chat` : pipeline RAG complet, réponse + sources +
abstention (memoire.md §7, §13). Route HTTP pure (§9).

Depuis la Phase 3, `GenerationService` reçoit un `HybridRetrievalService` au lieu du
`RetrievalService` vectoriel de la Phase 2 — sans aucune modification du code de
`GenerationService` lui-même, grâce au contrat public préservé (§3.1, voir
`hybrid_service.py`).

Depuis la Phase 5, protégée par `require_auth` : même logique ACL + temporalité que
`/api/v1/search` (voir `app/api/search/__init__.py`, `_resolve_authorized_version_ids`
dupliquée intentionnellement à l'identique plutôt que factorisée prématurément dans
un helper partagé — les deux routes restent indépendantes tant qu'un vrai besoin de
réutilisation au-delà de ces deux endroits n'apparaît pas).
"""
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app, g

from app.modules.generation.ollama_client import (
    OllamaEmbeddingClient,
    OllamaLLMClient,
    OllamaError,
)
from app.modules.retrieval.vector.chroma_store import ChromaVectorStore
from app.modules.retrieval.lexical.postgres_fts import PostgresFtsLexicalSearch
from app.modules.retrieval.reranker.cross_encoder import CrossEncoderReranker
from app.modules.retrieval.hybrid_service import HybridRetrievalService
from app.modules.generation.service import GenerationService
from app.modules.validation.service import ValidationService
from app.modules.validation.confidence_scorer import ConfidenceScorer
from app.modules.validation.contradiction_detector import ContradictionDetector
from app.modules.identity.decorators import require_auth
from app.modules.governance.access_control_service import AccessControlService
from app.modules.governance.temporal_resolver import TemporalResolver
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService
from app.modules.evaluation.graph_context_augmenter import build_graph_context_augmenter

chat_bp = Blueprint("chat", __name__)


def _build_generation_service(app_config) -> GenerationService:
    embedding_client = OllamaEmbeddingClient(
        base_url=app_config["OLLAMA_BASE_URL"],
        model=app_config["OLLAMA_EMBEDDING_MODEL"],
    )
    vector_store = ChromaVectorStore(
        persist_dir=app_config["CHROMA_PERSIST_DIR"],
        collection_name=app_config["CHROMA_COLLECTION_NAME"],
    )
    retrieval_service = HybridRetrievalService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        lexical_search=PostgresFtsLexicalSearch(),
        reranker=CrossEncoderReranker(model_name=app_config["RERANKER_MODEL_NAME"]),
        default_top_k=app_config.get("RETRIEVAL_TOP_K", 5),
        candidate_k=app_config.get("HYBRID_CANDIDATE_K", 20),
    )
    try:
        llm_client = OllamaLLMClient(
            base_url=app_config["OLLAMA_BASE_URL"],
            model=app_config["OLLAMA_LLM_MODEL"],
            temperature=app_config["OLLAMA_TEMPERATURE"],
            top_p=app_config["OLLAMA_TOP_P"],
            top_k=app_config["OLLAMA_TOP_K"],
        )
    except TypeError:
        # Compatibilité avec les doubles de test et les implémentations clientes
        # conservant l'ancien constructeur base_url/model.
        llm_client = OllamaLLMClient(
            base_url=app_config["OLLAMA_BASE_URL"],
            model=app_config["OLLAMA_LLM_MODEL"],
        )
    validation_service = ValidationService(
        confidence_scorer=ConfidenceScorer(),
        contradiction_detector=ContradictionDetector(),
        confidence_threshold=app_config.get("CONFIDENCE_THRESHOLD", 0.5),
    )
    context_augmenter = None
    try:
        graph_service = GraphService(
            Neo4jGraphStore(
                uri=app_config["NEO4J_URI"],
                user=app_config["NEO4J_USER"],
                password=app_config["NEO4J_PASSWORD"],
            )
        )
        context_augmenter = build_graph_context_augmenter(graph_service)
    except Exception:
        # Neo4j est optionnel : le RAG hybride continue sans enrichissement graphe.
        context_augmenter = None

    return GenerationService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        top_k=app_config.get("RETRIEVAL_TOP_K", 5),
        validation_service=validation_service,
        context_augmenter=context_augmenter,
    )


def _resolve_authorized_version_ids(user, as_of: datetime | None) -> set[int] | None:
    acl_ids = AccessControlService(
        admin_role_names=current_app.config["ADMIN_ROLE_NAMES"]
    ).get_authorized_document_version_ids(user)
    temporal_ids = TemporalResolver().get_valid_document_version_ids(as_of=as_of)
    if acl_ids is None:
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


@chat_bp.post("")
@require_auth
def chat():
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

    service = _build_generation_service(current_app.config)
    try:
        result = service.answer(query, top_k=top_k, authorized_document_version_ids=authorized_ids)
    except OllamaError as e:
        return (
            jsonify({"success": False, "data": None, "message": None, "error": str(e)}),
            503,
        )

    return jsonify(
        {
            "success": True,
            "data": {
                "answer": result.answer,
                "abstained": result.abstained,
                "reason": result.reason,
                "confidence": result.confidence,
                "warnings": result.warnings,
                "sources": [
                    {
                        "chunk_id": s.chunk_id,
                        "document_version_id": s.document_version_id,
                        "page": s.page,
                        "distance": s.distance,
                    }
                    for s in result.sources
                ],
            },
            "message": None,
            "error": None,
        }
    )
