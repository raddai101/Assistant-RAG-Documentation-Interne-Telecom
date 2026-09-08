"""
Blueprint `evaluation` — `POST /api/v1/evaluation/run` (Phase 8, memoire.md §2
objectif 9). Construit les 5 variantes de pipeline (LLM seul, RAG classique, Hybrid
RAG, KG-RAG, TEKIS complet) à partir de la config de l'app, puis délègue toute la
logique à `EvaluationRunner`. Route HTTP pure (§9).

Protégée par `require_auth` comme `/chat`/`/search` (§12 : pas de route exposant du
contenu du corpus sans identité).
"""
from flask import Blueprint, request, jsonify, current_app

from app.modules.generation.ollama_client import OllamaEmbeddingClient, OllamaLLMClient, OllamaError
from app.modules.retrieval.vector.chroma_store import ChromaVectorStore
from app.modules.retrieval.lexical.postgres_fts import PostgresFtsLexicalSearch
from app.modules.retrieval.reranker.cross_encoder import CrossEncoderReranker
from app.modules.retrieval.hybrid_service import HybridRetrievalService
from app.modules.retrieval.service import RetrievalService
from app.modules.generation.service import GenerationService
from app.modules.validation.service import ValidationService
from app.modules.validation.confidence_scorer import ConfidenceScorer
from app.modules.validation.contradiction_detector import ContradictionDetector
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService
from app.modules.identity.decorators import require_auth

from app.modules.evaluation.contracts import EvalQuestion, PipelineVariant
from app.modules.evaluation.variant_runners import GenerationServiceVariantRunner, LlmOnlyVariantRunner
from app.modules.evaluation.graph_context_augmenter import build_graph_context_augmenter
from app.modules.evaluation.runner import EvaluationRunner

evaluation_bp = Blueprint("evaluation", __name__)


def _build_embedding_and_llm(app_config):
    embedding_client = OllamaEmbeddingClient(
        base_url=app_config["OLLAMA_BASE_URL"], model=app_config["OLLAMA_EMBEDDING_MODEL"]
    )
    llm_client = OllamaLLMClient(base_url=app_config["OLLAMA_BASE_URL"], model=app_config["OLLAMA_LLM_MODEL"])
    return embedding_client, llm_client


def _build_validation_service(app_config) -> ValidationService:
    return ValidationService(
        confidence_scorer=ConfidenceScorer(),
        contradiction_detector=ContradictionDetector(),
        confidence_threshold=app_config.get("CONFIDENCE_THRESHOLD", 0.5),
    )


def _try_build_graph_service(app_config) -> GraphService | None:
    # Le Knowledge Graph est optionnel (memoire.md §10) : si Neo4j n'est pas
    # accessible, les variantes KG_RAG/TEKIS_COMPLETE tournent sans enrichissement
    # plutôt que d'échouer entièrement.
    try:
        graph_store = Neo4jGraphStore(
            uri=app_config["NEO4J_URI"], user=app_config["NEO4J_USER"], password=app_config["NEO4J_PASSWORD"]
        )
        return GraphService(graph_store)
    except Exception:
        return None


def _build_runners(app_config) -> dict[PipelineVariant, object]:
    embedding_client, llm_client = _build_embedding_and_llm(app_config)
    top_k = app_config.get("RETRIEVAL_TOP_K", 5)
    validation_service = _build_validation_service(app_config)

    vector_store = ChromaVectorStore(
        persist_dir=app_config["CHROMA_PERSIST_DIR"], collection_name=app_config["CHROMA_COLLECTION_NAME"]
    )

    vector_only_retrieval = RetrievalService(
        embedding_client=embedding_client, vector_store=vector_store, default_top_k=top_k
    )
    hybrid_retrieval = HybridRetrievalService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        lexical_search=PostgresFtsLexicalSearch(),
        reranker=CrossEncoderReranker(model_name=app_config["RERANKER_MODEL_NAME"]),
        default_top_k=top_k,
        candidate_k=app_config.get("HYBRID_CANDIDATE_K", 20),
    )

    graph_service = _try_build_graph_service(app_config)
    graph_augmenter = build_graph_context_augmenter(graph_service) if graph_service is not None else None

    runners = {
        PipelineVariant.LLM_ONLY: LlmOnlyVariantRunner(llm_client),
        PipelineVariant.VECTOR_ONLY: GenerationServiceVariantRunner(
            GenerationService(vector_only_retrieval, llm_client, top_k=top_k)
        ),
        PipelineVariant.HYBRID: GenerationServiceVariantRunner(
            GenerationService(hybrid_retrieval, llm_client, top_k=top_k)
        ),
        PipelineVariant.KG_RAG: GenerationServiceVariantRunner(
            GenerationService(hybrid_retrieval, llm_client, top_k=top_k, context_augmenter=graph_augmenter)
        ),
        PipelineVariant.TEKIS_COMPLETE: GenerationServiceVariantRunner(
            GenerationService(
                hybrid_retrieval,
                llm_client,
                top_k=top_k,
                validation_service=validation_service,
                context_augmenter=graph_augmenter,
            )
        ),
    }
    return runners


def _question_from_payload(payload: dict) -> EvalQuestion:
    return EvalQuestion(
        id=payload["id"],
        question=payload["question"],
        expected_chunk_ids=payload.get("expected_chunk_ids", []),
        expected_keywords=payload.get("expected_keywords", []),
        expects_abstention=payload.get("expects_abstention", False),
        authorized_document_version_ids=payload.get("authorized_document_version_ids"),
        forbidden_document_version_ids=payload.get("forbidden_document_version_ids", []),
    )


def _report_to_dict(report) -> dict:
    return {
        "variant": report.variant.value,
        "num_questions": report.num_questions,
        "mean_precision_at_k": report.mean_precision_at_k,
        "mean_recall_at_k": report.mean_recall_at_k,
        "mean_reciprocal_rank": report.mean_reciprocal_rank,
        "mean_keyword_coverage": report.mean_keyword_coverage,
        "abstention_accuracy": report.abstention_accuracy,
        "total_acl_leaks": report.total_acl_leaks,
        "mean_latency_ms": report.mean_latency_ms,
        "results": [
            {
                "question_id": r.question_id,
                "answer": r.answer,
                "abstained": r.abstained,
                "precision_at_k": r.precision_at_k,
                "recall_at_k": r.recall_at_k,
                "reciprocal_rank": r.reciprocal_rank,
                "keyword_coverage": r.keyword_coverage,
                "abstention_correct": r.abstention_correct,
                "acl_leaks": r.acl_leaks,
                "latency_ms": r.latency_ms,
            }
            for r in report.results
        ],
    }


@evaluation_bp.post("/run")
@require_auth
def run_evaluation():
    body = request.get_json(silent=True) or {}
    questions_payload = body.get("questions")
    if not questions_payload:
        return (
            jsonify(
                {"success": False, "data": None, "message": None, "error": "Le champ 'questions' est obligatoire et ne doit pas être vide."}
            ),
            400,
        )

    requested_variants = body.get("variants")  # None = toutes les variantes

    try:
        questions = [_question_from_payload(q) for q in questions_payload]
    except KeyError as e:
        return (
            jsonify({"success": False, "data": None, "message": None, "error": f"Champ manquant dans une question : {e}"}),
            400,
        )

    all_runners = _build_runners(current_app.config)
    if requested_variants:
        try:
            selected = {PipelineVariant(v): all_runners[PipelineVariant(v)] for v in requested_variants}
        except ValueError as e:
            return jsonify({"success": False, "data": None, "message": None, "error": str(e)}), 400
    else:
        selected = all_runners

    runner = EvaluationRunner(selected)

    try:
        reports = runner.run(questions)
    except OllamaError as e:
        return jsonify({"success": False, "data": None, "message": None, "error": str(e)}), 503

    return jsonify(
        {
            "success": True,
            "data": {variant.value: _report_to_dict(report) for variant, report in reports.items()},
            "message": None,
            "error": None,
        }
    )
