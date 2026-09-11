"""API d'exécution du benchmark A→G."""
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
from app.modules.evaluation.variant_runners import (
    LlmOnlyVariantRunner, RagVariantRunner, RagRerankVariantRunner,
    RagRerankMemoryVariantRunner, RagKgVariantRunner,
    RagKgRerankVariantRunner, RagKgRerankMemoryVariantRunner,
)
from app.modules.evaluation.graph_context_augmenter import build_graph_context_augmenter
from app.modules.evaluation.runner import EvaluationRunner


evaluation_bp = Blueprint("evaluation", __name__)


def _build_embedding_and_llm(c):
    return (
        OllamaEmbeddingClient(c["OLLAMA_BASE_URL"], c["OLLAMA_EMBEDDING_MODEL"]),
        OllamaLLMClient(c["OLLAMA_BASE_URL"], c["OLLAMA_LLM_MODEL"]),
    )


def _try_graph(c):
    try:
        return GraphService(Neo4jGraphStore(uri=c["NEO4J_URI"], user=c["NEO4J_USER"], password=c["NEO4J_PASSWORD"]))
    except Exception:
        return None


def _build_runners(c):
    embedding, llm = _build_embedding_and_llm(c)
    top_k = c.get("RETRIEVAL_TOP_K", 5)
    vector = ChromaVectorStore(persist_dir=c["CHROMA_PERSIST_DIR"], collection_name=c["CHROMA_COLLECTION_NAME"])
    rag = RetrievalService(embedding, vector, default_top_k=top_k)
    hybrid = HybridRetrievalService(
        embedding_client=embedding, vector_store=vector,
        lexical_search=PostgresFtsLexicalSearch(),
        reranker=CrossEncoderReranker(model_name=c["RERANKER_MODEL_NAME"]),
        default_top_k=top_k, candidate_k=c.get("HYBRID_CANDIDATE_K", 20),
    )
    graph = _try_graph(c)
    augmenter = build_graph_context_augmenter(graph) if graph else None
    validation = ValidationService(
        confidence_scorer=ConfidenceScorer(), contradiction_detector=ContradictionDetector(),
        confidence_threshold=c.get("CONFIDENCE_THRESHOLD", 0.5),
    )
    return {
        PipelineVariant.A_LLM_ONLY: LlmOnlyVariantRunner(llm),
        PipelineVariant.B_RAG: RagVariantRunner(GenerationService(rag, llm, top_k=top_k)),
        PipelineVariant.C_RAG_RERANK: RagRerankVariantRunner(GenerationService(hybrid, llm, top_k=top_k)),
        PipelineVariant.D_RAG_RERANK_MEMORY: RagRerankMemoryVariantRunner(GenerationService(hybrid, llm, top_k=top_k)),
        PipelineVariant.E_RAG_KG: RagKgVariantRunner(GenerationService(rag, llm, top_k=top_k, context_augmenter=augmenter)),
        PipelineVariant.F_RAG_KG_RERANK: RagKgRerankVariantRunner(GenerationService(hybrid, llm, top_k=top_k, context_augmenter=augmenter)),
        PipelineVariant.G_RAG_KG_RERANK_MEMORY: RagKgRerankMemoryVariantRunner(GenerationService(hybrid, llm, top_k=top_k, context_augmenter=augmenter)),
    }


def _question(payload):
    return EvalQuestion(
        id=payload["id"], question=payload["question"], reference_answer=payload.get("reference_answer"),
        expected_chunk_ids=payload.get("expected_chunk_ids", []), relevance_grades={int(k): v for k,v in payload.get("relevance_grades", {}).items()},
        expected_document_ids=payload.get("expected_document_ids", []), expected_document_version_ids=payload.get("expected_document_version_ids", []),
        expected_citations=payload.get("expected_citations", []), expected_keywords=payload.get("expected_keywords", []),
        expected_memory_facts=payload.get("expected_memory_facts", []), expected_kg_facts=payload.get("expected_kg_facts", []),
        expects_abstention=payload.get("expects_abstention", False), authorized_document_version_ids=payload.get("authorized_document_version_ids"),
        forbidden_document_version_ids=payload.get("forbidden_document_version_ids", []), conversation_history=payload.get("conversation_history", []), metadata=payload.get("metadata", {}),
    )


def _report(report):
    def result(r):
        d={k: getattr(r,k) for k in ("question_id","answer","abstained","precision_at_k","recall_at_k","reciprocal_rank","ndcg_at_k","keyword_coverage","faithfulness","answer_relevance","hallucination_rate","citation_precision","citation_recall","citation_completeness","version_accuracy","version_completeness","abstention_correct","acl_leaks","latency_ms","retrieved_chunk_ids","source_document_ids","source_document_version_ids","sources","error")}
        d["streaming"] = r.streaming.__dict__
        return d
    return {v.value: {k:getattr(r,k) for k in ("variant","num_questions","mean_precision_at_k","mean_recall_at_k","mean_reciprocal_rank","mean_ndcg_at_k","mean_keyword_coverage","mean_faithfulness","mean_answer_relevance","mean_hallucination_rate","mean_citation_precision","mean_citation_recall","mean_citation_completeness","mean_version_accuracy","mean_version_completeness","abstention_accuracy","total_acl_leaks","mean_latency_ms","mean_ttft_ms","mean_tokens_per_second","error_rate")} | {"results":[result(x) for x in r.results]} for v,r in report.items()}


@evaluation_bp.post("/run")
@require_auth
def run_evaluation():
    body=request.get_json(silent=True) or {}
    if not body.get("questions"):
        return jsonify({"success":False,"data":None,"message":None,"error":"Le champ 'questions' est obligatoire et ne doit pas être vide."}),400
    try:
        questions=[_question(q) for q in body["questions"]]
        all_runners=_build_runners(current_app.config)
        requested=body.get("variants")
        selected={PipelineVariant(v):all_runners[PipelineVariant(v)] for v in requested} if requested else all_runners
        runner=EvaluationRunner(selected, max_workers=int(body.get("parallel", current_app.config.get("EVALUATION_PARALLEL_WORKERS",4))), streaming=bool(body.get("streaming", False)))
        reports=runner.run(questions)
        return jsonify({"success":True,"data":_report(reports),"message":None,"error":None})
    except ValueError as e:
        return jsonify({"success":False,"data":None,"message":None,"error":str(e)}),400
    except OllamaError as e:
        return jsonify({"success":False,"data":None,"message":None,"error":str(e)}),503
