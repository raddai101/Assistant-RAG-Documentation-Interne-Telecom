"""
Adaptateurs normalisant chaque variante de pipeline (LLM seul, RAG classique, Hybrid
RAG, KG-RAG, TEKIS complet) vers une sortie comparable (`VariantOutcome`) — permet à
`EvaluationRunner` de rester indépendant du détail de chaque variante (§3.1).
"""
from typing import Protocol

from app.modules.generation.contracts import LLMClient
from app.modules.generation.service import GenerationService
from app.modules.evaluation.contracts import EvalQuestion, VariantOutcome


class VariantRunner(Protocol):
    def run(self, question: EvalQuestion) -> VariantOutcome: ...


class GenerationServiceVariantRunner:
    """Enveloppe un `GenerationService` déjà entièrement configuré (retrieval +
    validation + éventuel enrichissement KG) — couvre indifféremment VECTOR_ONLY,
    HYBRID, KG_RAG et TEKIS_COMPLETE selon ce qui a été injecté en amont dans le
    `GenerationService` fourni (voir `app/api/evaluation` pour la fabrique de chaque
    variante)."""

    def __init__(self, generation_service: GenerationService):
        self._generation_service = generation_service

    def run(self, question: EvalQuestion) -> VariantOutcome:
        authorized = (
            set(question.authorized_document_version_ids)
            if question.authorized_document_version_ids is not None
            else None
        )
        result = self._generation_service.answer(
            question.question, authorized_document_version_ids=authorized
        )
        return VariantOutcome(
            answer=result.answer,
            abstained=result.abstained,
            retrieved_chunk_ids=[s.chunk_id for s in result.sources if s.chunk_id is not None],
            source_document_version_ids=[
                s.document_version_id for s in result.sources if s.document_version_id is not None
            ],
        )


class LlmOnlyVariantRunner:
    """Baseline sans retrieval : le LLM répond uniquement à partir de ses
    connaissances internes, sans aucun extrait fourni — point de comparaison pour
    mesurer l'apport effectif du RAG (memoire.md §2 objectif 9)."""

    def __init__(self, llm_client: LLMClient):
        self._llm_client = llm_client

    def run(self, question: EvalQuestion) -> VariantOutcome:
        prompt = (
            "Réponds à la question suivante du mieux que tu peux, à partir de tes "
            f"connaissances générales.\n\nQuestion : {question.question}\n\nRéponse :"
        )
        answer = self._llm_client.generate(prompt)
        return VariantOutcome(
            answer=answer, abstained=False, retrieved_chunk_ids=[], source_document_version_ids=[]
        )
