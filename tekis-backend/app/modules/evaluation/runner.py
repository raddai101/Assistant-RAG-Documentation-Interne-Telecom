"""
Orchestrateur de l'évaluation comparative (Phase 8, memoire.md §2 objectif 9) :
LLM seul vs RAG classique vs Hybrid RAG vs KG-RAG vs TEKIS complet, sur des
métriques de retrieval, grounding (proxy lexical), sécurité (fuites ACL),
abstention et performance (latence).

Ce module ne construit pas lui-même les clients Ollama/ChromaDB/Neo4j — il reçoit
des `VariantRunner` déjà entièrement configurés (cohérent avec les fabriques déjà
utilisées par les routes `chat`/`search`, §9 : accès infrastructure isolés des
routes ET de l'orchestration).
"""
import time

from app.modules.evaluation.contracts import (
    EvalQuestion,
    QuestionEvalResult,
    VariantReport,
    PipelineVariant,
)
from app.modules.evaluation.variant_runners import VariantRunner
from app.modules.evaluation import metrics


class EvaluationRunner:
    def __init__(self, variant_runners: dict[PipelineVariant, VariantRunner]):
        self._variant_runners = variant_runners

    def run(self, questions: list[EvalQuestion]) -> dict[PipelineVariant, VariantReport]:
        return {
            variant: self._aggregate(variant, [self._run_one(runner, variant, q) for q in questions])
            for variant, runner in self._variant_runners.items()
        }

    def _run_one(self, runner: VariantRunner, variant: PipelineVariant, question: EvalQuestion) -> QuestionEvalResult:
        start = time.perf_counter()
        outcome = runner.run(question)
        latency_ms = (time.perf_counter() - start) * 1000

        relevant_ids = set(question.expected_chunk_ids)
        retrieved_ids = outcome.retrieved_chunk_ids
        k = len(retrieved_ids) or 1

        return QuestionEvalResult(
            question_id=question.id,
            variant=variant,
            answer=outcome.answer,
            abstained=outcome.abstained,
            precision_at_k=metrics.precision_at_k(retrieved_ids, relevant_ids, k),
            recall_at_k=metrics.recall_at_k(retrieved_ids, relevant_ids, k),
            reciprocal_rank=metrics.reciprocal_rank(retrieved_ids, relevant_ids),
            keyword_coverage=metrics.keyword_coverage(outcome.answer, question.expected_keywords),
            abstention_correct=metrics.abstention_correctness(question.expects_abstention, outcome.abstained),
            acl_leaks=metrics.acl_leak_count(
                outcome.source_document_version_ids, set(question.forbidden_document_version_ids)
            ),
            latency_ms=latency_ms,
        )

    @staticmethod
    def _aggregate(variant: PipelineVariant, results: list[QuestionEvalResult]) -> VariantReport:
        n = len(results) or 1
        return VariantReport(
            variant=variant,
            num_questions=len(results),
            mean_precision_at_k=sum(r.precision_at_k for r in results) / n,
            mean_recall_at_k=sum(r.recall_at_k for r in results) / n,
            mean_reciprocal_rank=sum(r.reciprocal_rank for r in results) / n,
            mean_keyword_coverage=sum(r.keyword_coverage for r in results) / n,
            abstention_accuracy=sum(1 for r in results if r.abstention_correct) / n,
            total_acl_leaks=sum(r.acl_leaks for r in results),
            mean_latency_ms=sum(r.latency_ms for r in results) / n,
            results=results,
        )
