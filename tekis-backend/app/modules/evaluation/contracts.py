"""Contrats du benchmark expérimental TEKIS A→G."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PipelineVariant(str, Enum):
    A_LLM_ONLY = "A_llm_only"
    B_RAG = "B_rag"
    C_RAG_RERANK = "C_rag_rerank"
    D_RAG_RERANK_MEMORY = "D_rag_rerank_memory"
    E_RAG_KG = "E_rag_kg"
    F_RAG_KG_RERANK = "F_rag_kg_rerank"
    G_RAG_KG_RERANK_MEMORY = "G_rag_kg_rerank_memory"
    # Compatibilité avec les noms de l'ancienne API d'évaluation.
    LLM_ONLY = A_LLM_ONLY
    VECTOR_ONLY = B_RAG
    HYBRID = C_RAG_RERANK
    KG_RAG = E_RAG_KG
    TEKIS_COMPLETE = G_RAG_KG_RERANK_MEMORY

    @property
    def label(self) -> str:
        return self.value.split("_", 1)[0]


@dataclass
class EvalQuestion:
    id: str
    question: str
    reference_answer: str | None = None
    expected_chunk_ids: list[int] = field(default_factory=list)
    relevance_grades: dict[int, float] = field(default_factory=dict)
    expected_document_ids: list[int] = field(default_factory=list)
    expected_document_version_ids: list[int] = field(default_factory=list)
    expected_citations: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    expected_memory_facts: list[str] = field(default_factory=list)
    expected_kg_facts: list[str] = field(default_factory=list)
    expects_abstention: bool = False
    authorized_document_version_ids: list[int] | None = None
    forbidden_document_version_ids: list[int] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingMetrics:
    ttft_ms: float | None = None
    generation_latency_ms: float | None = None
    total_latency_ms: float = 0.0
    token_count: int = 0
    tokens_per_second: float | None = None
    stream_completed: bool = False
    stream_error: str | None = None


@dataclass
class VariantOutcome:
    answer: str | None
    abstained: bool
    retrieved_chunk_ids: list[int] = field(default_factory=list)
    source_document_version_ids: list[int] = field(default_factory=list)
    source_document_ids: list[int] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    kg_context: str | None = None
    memory_used: bool = False
    streaming: StreamingMetrics | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuestionEvalResult:
    question_id: str
    variant: PipelineVariant
    answer: str | None
    abstained: bool
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float
    keyword_coverage: float
    faithfulness: float
    answer_relevance: float
    hallucination_rate: float
    citation_precision: float
    citation_recall: float
    citation_completeness: float
    version_accuracy: float
    version_completeness: float
    abstention_correct: bool
    acl_leaks: int
    latency_ms: float
    streaming: StreamingMetrics = field(default_factory=StreamingMetrics)
    retrieved_chunk_ids: list[int] = field(default_factory=list)
    source_document_ids: list[int] = field(default_factory=list)
    source_document_version_ids: list[int] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


@dataclass
class VariantReport:
    variant: PipelineVariant
    num_questions: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mean_reciprocal_rank: float
    mean_ndcg_at_k: float
    mean_keyword_coverage: float
    mean_faithfulness: float
    mean_answer_relevance: float
    mean_hallucination_rate: float
    mean_citation_precision: float
    mean_citation_recall: float
    mean_citation_completeness: float
    mean_version_accuracy: float
    mean_version_completeness: float
    abstention_accuracy: float
    total_acl_leaks: int
    mean_latency_ms: float
    mean_ttft_ms: float | None
    mean_tokens_per_second: float | None
    error_rate: float
    results: list[QuestionEvalResult] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    variants: dict[PipelineVariant, VariantReport]
    metadata: dict[str, Any] = field(default_factory=dict)
