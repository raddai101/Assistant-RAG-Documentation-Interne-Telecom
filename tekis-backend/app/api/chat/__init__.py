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
import time
import json

import logging

from flask import Blueprint, request, jsonify, current_app, g, Response, stream_with_context

from app.extensions import db
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
from app.models.document import DocumentVersion
from app.modules.conversations.service import ConversationService
from app.modules.governance.access_control_service import AccessControlService
from app.modules.governance.temporal_resolver import TemporalResolver
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService
from app.modules.evaluation.graph_context_augmenter import build_graph_context_augmenter

chat_bp = Blueprint("chat", __name__)
logger = logging.getLogger(__name__)

_GENERATION_SERVICE_KEY = "tekis_generation_service"
_CONVERSATION_SERVICE = ConversationService()


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


def _get_generation_service() -> GenerationService:
    """Retourne une instance réutilisée par le worker Flask/Gunicorn.

    Avant cette mise en cache, le pipeline complet (dont le CrossEncoder) était
    reconstruit à chaque question. Les modèles restent ainsi en mémoire entre deux
    requêtes, tout en restant isolés par worker Gunicorn.
    """
    service = current_app.extensions.get(_GENERATION_SERVICE_KEY)
    if service is None:
        started = time.perf_counter()
        service = _build_generation_service(current_app.config)
        current_app.extensions[_GENERATION_SERVICE_KEY] = service
        logger.info("[PERF] Initialisation du pipeline génération: %.3fs", time.perf_counter() - started)
    return service


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


def _serialize_source(source):
    version = None
    if source.document_version_id is not None:
        version = db.session.get(DocumentVersion, source.document_version_id)

    document = version.document if version else None
    return {
        "chunk_id": source.chunk_id,
        "document_id": version.document_id if version else None,
        "document_version_id": source.document_version_id,
        "page": source.page,
        "distance": source.distance,
        "document_title": document.title if document else None,
        "original_filename": version.original_filename if version else None,
        "file_type": version.file_type if version else None,
        "department_id": document.department_id if document else None,
        "department_name": (
            document.department.name
            if document and document.department
            else None
        ),
    }


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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

    # La conversation est créée avec le premier message. Les messages précédents
    # sont récupérés avant le nouveau message afin de constituer la mémoire sans
    # dupliquer la question courante dans le prompt.
    raw_conversation_id = body.get("conversation_id")
    conversation = None
    conversation_history = []
    try:
        conversation_id = int(raw_conversation_id) if raw_conversation_id is not None else None
    except (TypeError, ValueError):
        conversation_id = None

    if conversation_id is None:
        conversation = _CONVERSATION_SERVICE.create_for_first_message(
            g.current_user.id, query
        )
        conversation_id = conversation.id
    else:
        conversation = _CONVERSATION_SERVICE.ensure_owned(
            conversation_id, g.current_user.id
        )
        if conversation is None:
            return jsonify({
                "success": False, "data": None, "message": None,
                "error": "Conversation introuvable.",
            }), 404
        conversation_history = _CONVERSATION_SERVICE.recent_messages(
            conversation_id, g.current_user.id, limit=12
        )
        _CONVERSATION_SERVICE.add_user_message(conversation, query)

    started = time.perf_counter()
    acl_started = time.perf_counter()
    authorized_ids = _resolve_authorized_version_ids(g.current_user, as_of)
    logger.info("[PERF] chat ACL+temporal: %.3fs", time.perf_counter() - acl_started)

    service = _get_generation_service()

    # Compatibilité API : les clients JSON existants conservent le contrat historique.
    # Le frontend de chat demande explicitement text/event-stream pour bénéficier du
    # streaming token par token.
    if "text/event-stream" not in request.headers.get("Accept", ""):
        try:
            result = service.answer(
                query,
                top_k=top_k,
                authorized_document_version_ids=authorized_ids,
                conversation_history=conversation_history,
            )
        except OllamaError as e:
            return (
                jsonify({"success": False, "data": None, "message": None, "error": str(e)}),
                503,
            )
        if result.answer:
            _CONVERSATION_SERVICE.persist_assistant_async(
                current_app._get_current_object(),
                conversation_id,
                g.current_user.id,
                result.answer,
            )
        logger.info("[PERF] chat total: %.3fs", time.perf_counter() - started)
        return jsonify(
            {
                "success": True,
                "data": {
                    "answer": result.answer,
                    "abstained": result.abstained,
                    "reason": result.reason,
                    "confidence": result.confidence,
                    "warnings": result.warnings,
                    "sources": [_serialize_source(s) for s in result.sources],
                    "conversation_id": conversation_id,
                },
                "message": None,
                "error": None,
            }
        )

    @stream_with_context
    def generate_stream():
        try:
            # Événement immédiat : le frontend connaît la conversation avant même
            # que le retrieval/LLM ait terminé sa préparation.
            yield _sse_event("conversation", {"conversation_id": conversation_id})
            for item in service.stream_answer(
                query,
                top_k=top_k,
                authorized_document_version_ids=authorized_ids,
                conversation_history=conversation_history,
            ):
                # Le premier événement transmet l'identifiant de conversation au
                # frontend. La réponse reste ensuite streamée token par token.
                if item["type"] == "metadata":
                    item["data"]["conversation_id"] = conversation_id
                if item["type"] == "done" and item["data"].get("answer"):
                    _CONVERSATION_SERVICE.persist_assistant_async(
                        current_app._get_current_object(),
                        conversation_id,
                        g.current_user.id,
                        item["data"]["answer"],
                    )
                yield _sse_event(item["type"], item["data"])
        except OllamaError as e:
            logger.exception("[CHAT] erreur Ollama pendant le streaming")
            yield _sse_event("error", {"error": str(e)})
        except Exception as e:
            logger.exception("[CHAT] erreur pendant le streaming")
            yield _sse_event("error", {"error": "Erreur interne du backend."})
        finally:
            logger.info("[PERF] chat streaming total: %.3fs", time.perf_counter() - started)

    return Response(
        generate_stream(),
        status=200,
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

