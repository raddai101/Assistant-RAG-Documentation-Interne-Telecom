from app.modules.evaluation.contracts import EvalQuestion, VariantOutcome, PipelineVariant
from app.modules.evaluation.runner import EvaluationRunner


class FakeVariantRunner:
    def __init__(self, outcomes_by_question_id: dict[str, VariantOutcome]):
        self._outcomes = outcomes_by_question_id

    def run(self, question):
        return self._outcomes[question.id]


def test_run_aggregates_metrics_across_questions():
    q1 = EvalQuestion(id="q1", question="Question 1", expected_chunk_ids=[1, 2], expected_keywords=["panne"])
    q2 = EvalQuestion(id="q2", question="Question 2", expected_chunk_ids=[3])

    runner = EvaluationRunner(
        {
            PipelineVariant.VECTOR_ONLY: FakeVariantRunner(
                {
                    "q1": VariantOutcome(answer="La panne dure longtemps.", abstained=False, retrieved_chunk_ids=[1, 5]),
                    "q2": VariantOutcome(answer="Réponse ok.", abstained=False, retrieved_chunk_ids=[3]),
                }
            )
        }
    )

    reports = runner.run([q1, q2])
    report = reports[PipelineVariant.VECTOR_ONLY]

    assert report.num_questions == 2
    assert report.mean_recall_at_k == (0.5 + 1.0) / 2  # q1: 1/2 trouvé, q2: 1/1 trouvé
    assert len(report.results) == 2


def test_run_computes_abstention_accuracy():
    q1 = EvalQuestion(id="q1", question="Hors corpus", expects_abstention=True)
    q2 = EvalQuestion(id="q2", question="Dans le corpus", expects_abstention=False)

    runner = EvaluationRunner(
        {
            PipelineVariant.HYBRID: FakeVariantRunner(
                {
                    "q1": VariantOutcome(answer=None, abstained=True),  # correct
                    "q2": VariantOutcome(answer=None, abstained=True),  # incorrect
                }
            )
        }
    )

    report = runner.run([q1, q2])[PipelineVariant.HYBRID]

    assert report.abstention_accuracy == 0.5


def test_run_detects_acl_leaks():
    q1 = EvalQuestion(id="q1", question="Question restreinte", forbidden_document_version_ids=[99])

    runner = EvaluationRunner(
        {
            PipelineVariant.TEKIS_COMPLETE: FakeVariantRunner(
                {"q1": VariantOutcome(answer="ok", abstained=False, source_document_version_ids=[99, 1])}
            )
        }
    )

    report = runner.run([q1])[PipelineVariant.TEKIS_COMPLETE]

    assert report.total_acl_leaks == 1


def test_run_handles_multiple_variants_independently():
    q1 = EvalQuestion(id="q1", question="Question", expected_chunk_ids=[1])

    runner = EvaluationRunner(
        {
            PipelineVariant.LLM_ONLY: FakeVariantRunner({"q1": VariantOutcome(answer="a", abstained=False)}),
            PipelineVariant.HYBRID: FakeVariantRunner(
                {"q1": VariantOutcome(answer="b", abstained=False, retrieved_chunk_ids=[1])}
            ),
        }
    )

    reports = runner.run([q1])

    assert reports[PipelineVariant.LLM_ONLY].mean_recall_at_k == 0.0
    assert reports[PipelineVariant.HYBRID].mean_recall_at_k == 1.0


def test_run_empty_questions_list_returns_zeroed_report():
    runner = EvaluationRunner({PipelineVariant.HYBRID: FakeVariantRunner({})})

    report = runner.run([])[PipelineVariant.HYBRID]

    assert report.num_questions == 0
    assert report.results == []
