"""
Contrats du module `evaluation` (Phase 8, memoire.md §2 objectif 9) : comparaison
LLM seul vs RAG classique (vectoriel) vs Hybrid RAG vs KG-RAG vs TEKIS complet, sur
des métriques de retrieval, grounding, hallucination, sécurité, abstention et
performance.
"""
from dataclasses import dataclass, field
from enum import Enum


class PipelineVariant(str, Enum):
    LLM_ONLY = "llm_only"
    VECTOR_ONLY = "vector_only"  # RAG classique (Phase 2 baseline)
    HYBRID = "hybrid"  # Hybrid RAG (Phase 3 : fusion lexicale+vectorielle + reranking)
    KG_RAG = "kg_rag"  # Hybrid + enrichissement Knowledge Graph (Phase 4/7)
    TEKIS_COMPLETE = "tekis_complete"  # Hybrid + KG + ACL/temporel (Phase 5) + validation (Phase 6)


@dataclass
class EvalQuestion:
    id: str
    question: str
    expected_chunk_ids: list[int] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    expects_abstention: bool = False
    # None = pas de restriction ACL testée pour cette question. Une liste (même
    # vide) active le filtrage ACL/temporel (Phase 5) pour cette question.
    authorized_document_version_ids: list[int] | None = None
    # Versions que la question ne devrait JAMAIS voir apparaître dans les sources
    # (cas de test sécurité — memoire.md §12).
    forbidden_document_version_ids: list[int] = field(default_factory=list)


@dataclass
class QuestionEvalResult:
    question_id: str
    variant: PipelineVariant
    answer: str | None
    abstained: bool
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    keyword_coverage: float
    abstention_correct: bool
    acl_leaks: int
    latency_ms: float


@dataclass
class VariantReport:
    variant: PipelineVariant
    num_questions: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mean_reciprocal_rank: float
    mean_keyword_coverage: float
    abstention_accuracy: float
    total_acl_leaks: int
    mean_latency_ms: float
    results: list[QuestionEvalResult] = field(default_factory=list)


@dataclass
class VariantOutcome:
    """Sortie normalisée d'une variante de pipeline, indépendante de son
    implémentation interne — permet à `EvaluationRunner` de rester agnostique du
    détail de chaque variante (§3.1 « CHANGE IMPLEMENTATION, PRESERVE CONTRACT »)."""

    answer: str | None
    abstained: bool
    retrieved_chunk_ids: list[int] = field(default_factory=list)
    source_document_version_ids: list[int] = field(default_factory=list)
