"""Runner parallèle du benchmark A→G."""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.modules.evaluation import metrics
from app.modules.evaluation.contracts import (
    EvalQuestion, PipelineVariant, QuestionEvalResult, VariantReport, BenchmarkReport,
)
from app.modules.evaluation.variant_runners import VariantRunner


class EvaluationRunner:
    def __init__(self, variant_runners: dict[PipelineVariant, VariantRunner], max_workers: int = 4, streaming: bool = False):
        self._variant_runners = variant_runners
        self._max_workers = max(1, max_workers)
        self._streaming = streaming

    def run(self, questions: list[EvalQuestion]) -> dict[PipelineVariant, VariantReport]:
        jobs = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            for variant, runner in self._variant_runners.items():
                for question in questions:
                    jobs.append(pool.submit(self._run_one, runner, variant, question))
            results_by_variant = {v: [] for v in self._variant_runners}
            for future in as_completed(jobs):
                result = future.result()
                results_by_variant[result.variant].append(result)
        return {
            variant: self._aggregate(variant, sorted(results, key=lambda r: r.question_id))
            for variant, results in results_by_variant.items()
        }

    def run_report(self, questions: list[EvalQuestion], metadata=None) -> BenchmarkReport:
        return BenchmarkReport(self.run(questions), metadata or {})

    def _run_one(self, runner, variant, question):
        started = time.perf_counter()
        error = None
        try:
            outcome = runner.stream(question) if self._streaming and hasattr(runner, "stream") else runner.run(question)
        except Exception as exc:
            outcome = None
            error = str(exc)
        latency_ms = (time.perf_counter() - started) * 1000
        if outcome is None:
            outcome = type("Outcome", (), {"answer": None, "abstained": False, "retrieved_chunk_ids": [], "source_document_version_ids": [], "source_document_ids": [], "sources": [], "streaming": None})()
        retrieved = outcome.retrieved_chunk_ids
        relevant = set(question.expected_chunk_ids)
        k = len(retrieved) or 1
        cp, cr, cc = metrics.citation_metrics(outcome.answer, question.expected_citations)
        va, vc = metrics.version_metrics(outcome.source_document_version_ids, question.expected_document_version_ids)
        sm = outcome.streaming
        return QuestionEvalResult(
            question_id=question.id, variant=variant, answer=outcome.answer, abstained=outcome.abstained,
            precision_at_k=metrics.precision_at_k(retrieved, relevant, k),
            recall_at_k=metrics.recall_at_k(retrieved, relevant, k),
            reciprocal_rank=metrics.reciprocal_rank(retrieved, relevant),
            ndcg_at_k=metrics.ndcg_at_k(retrieved, question.relevance_grades or {i: 1 for i in relevant}, k),
            keyword_coverage=metrics.keyword_coverage(outcome.answer, question.expected_keywords),
            faithfulness=metrics.faithfulness_score(outcome.answer, question.expected_keywords),
            answer_relevance=metrics.answer_relevance_score(outcome.answer, question.expected_keywords),
            hallucination_rate=metrics.hallucination_rate(outcome.answer, question.expected_keywords),
            citation_precision=cp, citation_recall=cr, citation_completeness=cc,
            version_accuracy=va, version_completeness=vc,
            abstention_correct=metrics.abstention_correctness(question.expects_abstention, outcome.abstained),
            acl_leaks=metrics.acl_leak_count(outcome.source_document_version_ids, set(question.forbidden_document_version_ids)),
            latency_ms=latency_ms, streaming=sm or __import__('app.modules.evaluation.contracts', fromlist=['StreamingMetrics']).StreamingMetrics(),
            retrieved_chunk_ids=retrieved, source_document_ids=outcome.source_document_ids,
            source_document_version_ids=outcome.source_document_version_ids, sources=outcome.sources, error=error,
        )

    @staticmethod
    def _aggregate(variant, results):
        n = len(results)
        avg = lambda attr: (sum(getattr(r, attr) for r in results) / n) if n else 0.0
        ttft = [r.streaming.ttft_ms for r in results if r.streaming.ttft_ms is not None]
        tps = [r.streaming.tokens_per_second for r in results if r.streaming.tokens_per_second is not None]
        return VariantReport(
            variant=variant, num_questions=n,
            mean_precision_at_k=avg("precision_at_k"), mean_recall_at_k=avg("recall_at_k"),
            mean_reciprocal_rank=avg("reciprocal_rank"), mean_ndcg_at_k=avg("ndcg_at_k"),
            mean_keyword_coverage=avg("keyword_coverage"), mean_faithfulness=avg("faithfulness"),
            mean_answer_relevance=avg("answer_relevance"), mean_hallucination_rate=avg("hallucination_rate"),
            mean_citation_precision=avg("citation_precision"), mean_citation_recall=avg("citation_recall"),
            mean_citation_completeness=avg("citation_completeness"), mean_version_accuracy=avg("version_accuracy"),
            mean_version_completeness=avg("version_completeness"), abstention_accuracy=(sum(r.abstention_correct for r in results)/n if n else 0.0),
            total_acl_leaks=sum(r.acl_leaks for r in results), mean_latency_ms=avg("latency_ms"),
            mean_ttft_ms=sum(ttft)/len(ttft) if ttft else None, mean_tokens_per_second=sum(tps)/len(tps) if tps else None,
            error_rate=sum(bool(r.error or r.streaming.stream_error) for r in results)/n if n else 0.0,
            results=results,
        )
