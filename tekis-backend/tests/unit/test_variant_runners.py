from app.modules.evaluation.contracts import EvalQuestion
from app.modules.evaluation.variant_runners import GenerationServiceVariantRunner, LlmOnlyVariantRunner


class FakeLLMClient:
    def __init__(self, response="Réponse générée factice."):
        self._response = response
        self.last_prompt = None

    def generate(self, prompt):
        self.last_prompt = prompt
        return self._response


class FakeSourceRef:
    def __init__(self, chunk_id, document_version_id):
        self.chunk_id = chunk_id
        self.document_version_id = document_version_id


class FakeGenerationResult:
    def __init__(self, answer, abstained, sources):
        self.answer = answer
        self.abstained = abstained
        self.sources = sources


class FakeGenerationService:
    def __init__(self, result: FakeGenerationResult):
        self._result = result
        self.last_call_kwargs = None

    def answer(self, query, top_k=None, authorized_document_version_ids=None):
        self.last_call_kwargs = {
            "query": query,
            "top_k": top_k,
            "authorized_document_version_ids": authorized_document_version_ids,
        }
        return self._result


def test_llm_only_runner_calls_generate_with_no_retrieval_context():
    llm_client = FakeLLMClient(response="Réponse sans aucun extrait fourni.")
    runner = LlmOnlyVariantRunner(llm_client)
    question = EvalQuestion(id="q1", question="Quelle est la procédure X ?")

    outcome = runner.run(question)

    assert outcome.answer == "Réponse sans aucun extrait fourni."
    assert outcome.abstained is False
    assert outcome.retrieved_chunk_ids == []
    assert outcome.source_document_version_ids == []
    assert "Quelle est la procédure X ?" in llm_client.last_prompt


def test_generation_service_runner_normalizes_outcome():
    sources = [FakeSourceRef(chunk_id=5, document_version_id=2), FakeSourceRef(chunk_id=6, document_version_id=2)]
    fake_service = FakeGenerationService(FakeGenerationResult(answer="Réponse sourcée.", abstained=False, sources=sources))
    runner = GenerationServiceVariantRunner(fake_service)
    question = EvalQuestion(id="q1", question="Question test")

    outcome = runner.run(question)

    assert outcome.answer == "Réponse sourcée."
    assert outcome.retrieved_chunk_ids == [5, 6]
    assert outcome.source_document_version_ids == [2, 2]


def test_generation_service_runner_passes_authorized_ids_when_provided():
    fake_service = FakeGenerationService(FakeGenerationResult(answer=None, abstained=True, sources=[]))
    runner = GenerationServiceVariantRunner(fake_service)
    question = EvalQuestion(id="q1", question="Question ACL", authorized_document_version_ids=[1, 2])

    runner.run(question)

    assert fake_service.last_call_kwargs["authorized_document_version_ids"] == {1, 2}


def test_generation_service_runner_passes_none_when_not_restricted():
    fake_service = FakeGenerationService(FakeGenerationResult(answer="ok", abstained=False, sources=[]))
    runner = GenerationServiceVariantRunner(fake_service)
    question = EvalQuestion(id="q1", question="Question libre")

    runner.run(question)

    assert fake_service.last_call_kwargs["authorized_document_version_ids"] is None
