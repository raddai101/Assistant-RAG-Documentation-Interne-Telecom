"""Runners A→G partageant les mêmes composants TEKIS."""
import time
from typing import Protocol

from app.modules.generation.contracts import LLMClient
from app.modules.generation.service import GenerationService
from app.modules.evaluation.contracts import EvalQuestion, VariantOutcome, StreamingMetrics


class VariantRunner(Protocol):
    def run(self, question: EvalQuestion) -> VariantOutcome: ...
    def stream(self, question: EvalQuestion) -> VariantOutcome: ...


class _GenerationRunner:
    def __init__(self, generation_service: GenerationService, use_memory: bool = False):
        self._generation_service = generation_service
        self._use_memory = use_memory

    def _history(self, q: EvalQuestion):
        return q.conversation_history if self._use_memory else None

    def run(self, question: EvalQuestion) -> VariantOutcome:
        authorized = set(question.authorized_document_version_ids) if question.authorized_document_version_ids is not None else None
        result = self._generation_service.answer(
            question.question,
            authorized_document_version_ids=authorized,
            conversation_history=self._history(question),
        )
        return self._outcome(result, self._use_memory)

    def stream(self, question: EvalQuestion) -> VariantOutcome:
        authorized = set(question.authorized_document_version_ids) if question.authorized_document_version_ids is not None else None
        started = time.perf_counter()
        first = None
        chunks = []
        metadata = None
        completed = False
        error = None
        try:
            for event in self._generation_service.stream_answer(
                question.question,
                authorized_document_version_ids=authorized,
                conversation_history=self._history(question),
            ):
                if event["type"] == "metadata":
                    metadata = event["data"]
                elif event["type"] == "token":
                    if first is None:
                        first = time.perf_counter()
                    chunks.append(event["data"].get("text", ""))
                elif event["type"] == "done":
                    completed = True
                    if not chunks and event["data"].get("answer"):
                        chunks.append(event["data"]["answer"])
        except Exception as exc:
            error = str(exc)
        end = time.perf_counter()
        answer = "".join(chunks) or None
        sources = (metadata or {}).get("sources", [])
        vids = [s.get("document_version_id") for s in sources if s.get("document_version_id") is not None]
        dids = [s.get("document_id") for s in sources if s.get("document_id") is not None]
        cids = [s.get("chunk_id") for s in sources if s.get("chunk_id") is not None]
        gen_start = first or started
        total_ms = (end - started) * 1000
        gen_ms = (end - gen_start) * 1000
        token_count = len(chunks)
        stream = StreamingMetrics(
            ttft_ms=((first - started) * 1000) if first else None,
            generation_latency_ms=gen_ms,
            total_latency_ms=total_ms,
            token_count=token_count,
            tokens_per_second=(token_count / (gen_ms / 1000)) if gen_ms > 0 and token_count else None,
            stream_completed=completed,
            stream_error=error,
        )
        return VariantOutcome(
            answer=answer,
            abstained=(metadata or {}).get("abstained", not bool(answer)),
            retrieved_chunk_ids=cids,
            source_document_version_ids=vids,
            source_document_ids=dids,
            sources=sources,
            memory_used=self._use_memory,
            streaming=stream,
            metadata={"error": error} if error else {},
        )

    @staticmethod
    def _outcome(result, memory_used=False):
        sources = [GenerationService._source_to_dict(s) for s in result.sources]
        return VariantOutcome(
            answer=result.answer,
            abstained=result.abstained,
            retrieved_chunk_ids=[s.chunk_id for s in result.sources if s.chunk_id is not None],
            source_document_version_ids=[s.document_version_id for s in result.sources if s.document_version_id is not None],
            source_document_ids=[s.document_id for s in result.sources if s.document_id is not None],
            sources=sources,
            memory_used=memory_used,
        )


class GenerationServiceVariantRunner(_GenerationRunner):
    pass


class RagVariantRunner(_GenerationRunner):
    pass


class RagRerankVariantRunner(_GenerationRunner):
    pass


class RagRerankMemoryVariantRunner(_GenerationRunner):
    pass


class RagKgVariantRunner(_GenerationRunner):
    pass


class RagKgRerankVariantRunner(_GenerationRunner):
    pass


class RagKgRerankMemoryVariantRunner(_GenerationRunner):
    pass


class LlmOnlyVariantRunner:
    def __init__(self, llm_client: LLMClient, use_memory: bool = False):
        self._llm_client = llm_client
        self._use_memory = use_memory

    def _prompt(self, q: EvalQuestion) -> str:
        history = ""
        if self._use_memory and q.conversation_history:
            history = "\nHistorique de discussion:\n" + "\n".join(
                f"{m.get('role', 'user')}: {m.get('content', '')}" for m in q.conversation_history
            ) + "\n"
        return f"Réponds à la question suivante du mieux que tu peux, sans accès à un corpus documentaire.\n{history}\nQuestion : {q.question}\n\nRéponse :"

    def run(self, question: EvalQuestion) -> VariantOutcome:
        return VariantOutcome(answer=self._llm_client.generate(self._prompt(question)), abstained=False, memory_used=self._use_memory)

    def stream(self, question: EvalQuestion) -> VariantOutcome:
        started = time.perf_counter(); first = None; chunks = []; error = None; completed = False
        try:
            for token in self._llm_client.stream(self._prompt(question)):
                if first is None: first = time.perf_counter()
                chunks.append(token)
            completed = True
        except Exception as exc:
            error = str(exc)
        end = time.perf_counter(); answer = "".join(chunks) or None
        gen_ms = (end - (first or started)) * 1000
        count = len(chunks)
        return VariantOutcome(
            answer=answer, abstained=False, memory_used=self._use_memory,
            streaming=StreamingMetrics(
                ttft_ms=((first-started)*1000) if first else None,
                generation_latency_ms=gen_ms,
                total_latency_ms=(end-started)*1000,
                token_count=count,
                tokens_per_second=(count/(gen_ms/1000)) if gen_ms > 0 and count else None,
                stream_completed=completed,
                stream_error=error,
            ),
        )
