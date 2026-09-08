import pytest

from app.modules.retrieval.contracts import VectorSearchResult
from app.modules.retrieval.service import RetrievalService
from app.modules.generation.service import GenerationService


class FakeEmbeddingClient:
    def embed(self, texts):
        return [[float(len(t))] for t in texts]


class FakeVectorStore:
    def __init__(self, results):
        self._results = results
        self.last_query_embedding = None
        self.last_top_k = None
        self.last_where = None

    def search(self, query_embedding, top_k, where=None):
        self.last_query_embedding = query_embedding
        self.last_top_k = top_k
        self.last_where = where
        return self._results[:top_k]


class FakeLLMClient:
    def __init__(self, response="Réponse générée."):
        self.response = response
        self.last_prompt = None

    def generate(self, prompt):
        self.last_prompt = prompt
        return self.response


class FakeValidationService:
    """Phase 6 : `GenerationService` dépend désormais de `ValidationService`, qui
    accède à la DB via `ContradictionDetector` (`ValidationRepository`). Ce fake
    permet de garder ces tests comme des tests unitaires purs, sans contexte
    applicatif Flask ni base de données — le comportement réel de la validation
    est testé séparément dans `test_validation_module.py`."""

    def __init__(self, should_abstain=False, confidence=1.0, warnings=None, reason=None):
        from app.modules.validation.contracts import ValidationOutcome

        self._outcome = ValidationOutcome(
            confidence=confidence,
            warnings=warnings or [],
            should_abstain=should_abstain,
            abstain_reason=reason,
        )

    def validate(self, results):
        return self._outcome


def test_retrieval_service_embeds_query_and_searches_vector_store():
    fake_results = [VectorSearchResult(id="chunk-1", document="contenu 1", metadata={"chunk_id": 1})]
    vector_store = FakeVectorStore(fake_results)
    service = RetrievalService(
        embedding_client=FakeEmbeddingClient(), vector_store=vector_store, default_top_k=3
    )

    result = service.search("ma question")

    assert result.results == fake_results
    assert vector_store.last_query_embedding == [len("ma question")]
    assert vector_store.last_top_k == 3


def test_retrieval_service_respects_explicit_top_k():
    vector_store = FakeVectorStore([])
    service = RetrievalService(embedding_client=FakeEmbeddingClient(), vector_store=vector_store, default_top_k=5)

    service.search("question", top_k=1)

    assert vector_store.last_top_k == 1


def test_retrieval_service_passes_where_filter_when_authorized_ids_given():
    vector_store = FakeVectorStore([])
    service = RetrievalService(embedding_client=FakeEmbeddingClient(), vector_store=vector_store)

    service.search("question", authorized_document_version_ids={3, 7})

    assert vector_store.last_where == {"document_version_id": {"$in": [3, 7]}} or \
        set(vector_store.last_where["document_version_id"]["$in"]) == {3, 7}


def test_retrieval_service_denies_without_querying_when_authorized_ids_empty():
    vector_store = FakeVectorStore([VectorSearchResult(id="x", document="secret", metadata={})])
    service = RetrievalService(embedding_client=FakeEmbeddingClient(), vector_store=vector_store)

    result = service.search("question", authorized_document_version_ids=set())

    assert result.results == []
    assert vector_store.last_query_embedding is None  # jamais interrogé


def test_retrieval_service_no_restriction_when_authorized_ids_is_none():
    vector_store = FakeVectorStore([])
    service = RetrievalService(embedding_client=FakeEmbeddingClient(), vector_store=vector_store)

    service.search("question", authorized_document_version_ids=None)

    assert vector_store.last_where is None


def test_generation_service_returns_answer_with_sources():
    fake_results = [
        VectorSearchResult(
            id="chunk-1",
            document="La procédure SGSN impose...",
            metadata={"chunk_id": 1, "document_version_id": 10, "page": 2},
            distance=0.12,
        )
    ]
    retrieval_service = RetrievalService(
        embedding_client=FakeEmbeddingClient(),
        vector_store=FakeVectorStore(fake_results),
        default_top_k=5,
    )
    llm_client = FakeLLMClient(response="Voici la procédure SGSN.")
    service = GenerationService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        validation_service=FakeValidationService(confidence=0.9),
    )

    result = service.answer("Quelle est la procédure SGSN ?")

    assert result.abstained is False
    assert result.answer == "Voici la procédure SGSN."
    assert result.confidence == 0.9
    assert len(result.sources) == 1
    assert result.sources[0].chunk_id == 1
    assert result.sources[0].document_version_id == 10
    assert result.sources[0].page == 2
    assert "La procédure SGSN impose..." in llm_client.last_prompt
    assert "Quelle est la procédure SGSN ?" in llm_client.last_prompt


def test_generation_service_abstains_when_no_retrieval_results():
    retrieval_service = RetrievalService(
        embedding_client=FakeEmbeddingClient(), vector_store=FakeVectorStore([]), default_top_k=5
    )
    llm_client = FakeLLMClient()
    service = GenerationService(
        retrieval_service=retrieval_service, llm_client=llm_client, validation_service=FakeValidationService()
    )

    result = service.answer("Question hors corpus ?")

    assert result.abstained is True
    assert result.answer is None
    assert result.sources == []
    assert result.reason is not None
    assert llm_client.last_prompt is None  # le LLM ne doit JAMAIS être appelé sans preuve


def test_generation_service_abstains_when_validation_confidence_too_low():
    """Phase 6 : nouvelle abstention, distincte de « aucun résultat » — ici le
    retrieval renvoie bien un résultat, mais la validation juge la confiance
    insuffisante. Le LLM ne doit toujours jamais être appelé."""
    fake_results = [VectorSearchResult(id="chunk-1", document="peu pertinent", metadata={})]
    retrieval_service = RetrievalService(
        embedding_client=FakeEmbeddingClient(), vector_store=FakeVectorStore(fake_results), default_top_k=5
    )
    llm_client = FakeLLMClient()
    service = GenerationService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        validation_service=FakeValidationService(
            should_abstain=True, confidence=0.1, reason="Confiance insuffisante (0.10 < seuil 0.50)."
        ),
    )

    result = service.answer("Question ambiguë ?")

    assert result.abstained is True
    assert result.answer is None
    assert result.confidence == 0.1
    assert "Confiance insuffisante" in result.reason
    assert llm_client.last_prompt is None


def test_generation_service_uses_context_augmenter_when_provided():
    """Phase 8 : `context_augmenter` est un ajout rétrocompatible (défaut `None`,
    voir tests ci-dessus qui ne le fournissent pas et continuent de passer
    inchangés). Ce test vérifie que, quand il est fourni, son résultat est bien
    injecté dans le prompt envoyé au LLM."""
    fake_results = [VectorSearchResult(id="chunk-1", document="contenu pertinent", metadata={"chunk_id": 1})]
    retrieval_service = RetrievalService(
        embedding_client=FakeEmbeddingClient(), vector_store=FakeVectorStore(fake_results), default_top_k=5
    )
    llm_client = FakeLLMClient()

    def fake_augmenter(results):
        assert len(results) == 1
        return "Entités du graphe de connaissances liées à ces extraits :\n- Équipe Réseau (Department)"

    service = GenerationService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        validation_service=FakeValidationService(should_abstain=False, confidence=0.9),
        context_augmenter=fake_augmenter,
    )

    service.answer("Question ?")

    assert "Équipe Réseau" in llm_client.last_prompt


def test_generation_service_without_context_augmenter_unchanged():
    """Comportement par défaut (Phases 2-6) strictement inchangé quand
    `context_augmenter` n'est pas fourni."""
    fake_results = [VectorSearchResult(id="chunk-1", document="contenu pertinent", metadata={"chunk_id": 1})]
    retrieval_service = RetrievalService(
        embedding_client=FakeEmbeddingClient(), vector_store=FakeVectorStore(fake_results), default_top_k=5
    )
    llm_client = FakeLLMClient()

    service = GenerationService(
        retrieval_service=retrieval_service,
        llm_client=llm_client,
        validation_service=FakeValidationService(should_abstain=False, confidence=0.9),
    )

    service.answer("Question ?")

    assert "Entités du graphe" not in llm_client.last_prompt
