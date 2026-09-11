"""Métriques pures du benchmark TEKIS."""
import math
import re
from typing import Iterable


def precision_at_k(retrieved_ids: list[int], relevant_ids: set[int], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    return (sum(cid in relevant_ids for cid in top_k) / len(top_k)) if top_k else 0.0


def recall_at_k(retrieved_ids: list[int], relevant_ids: set[int], k: int) -> float:
    if not relevant_ids:
        return 0.0
    return sum(cid in relevant_ids for cid in retrieved_ids[:k]) / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    for rank, cid in enumerate(retrieved_ids, 1):
        if cid in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[int], relevance_grades: dict[int, float], k: int) -> float:
    if k <= 0 or not relevance_grades:
        return 0.0
    dcg = sum((2 ** max(float(relevance_grades.get(cid, 0.0)), 0.0) - 1) / math.log2(rank + 1)
              for rank, cid in enumerate(retrieved_ids[:k], 1))
    ideal = sorted((max(float(v), 0.0) for v in relevance_grades.values()), reverse=True)[:k]
    idcg = sum((2 ** grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, 1))
    return dcg / idcg if idcg else 0.0


def keyword_coverage(answer: str | None, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    if not answer:
        return 0.0
    text = answer.casefold()
    return sum(kw.casefold() in text for kw in expected_keywords) / len(expected_keywords)


def abstention_correctness(expected_abstain: bool, actual_abstained: bool) -> bool:
    return expected_abstain == actual_abstained


def acl_leak_count(source_document_version_ids: list[int], forbidden_version_ids: set[int]) -> int:
    return sum(vid in forbidden_version_ids for vid in source_document_version_ids) if forbidden_version_ids else 0


def citation_metrics(answer: str | None, expected_citations: Iterable[str]) -> tuple[float, float, float]:
    expected = [str(x).casefold() for x in expected_citations if str(x).strip()]
    if not expected:
        return 1.0, 1.0, 1.0
    text = (answer or "").casefold()
    hits = sum(c in text for c in expected)
    precision = hits / max(1, _citation_mentions(answer))
    recall = hits / len(expected)
    completeness = recall
    return min(precision, 1.0), recall, completeness


def _citation_mentions(answer: str | None) -> int:
    if not answer:
        return 0
    # Human-readable citation names are expected; numeric-only IDs are not counted.
    matches = re.findall(r"(?:source|document|réf(?:érence)?|citation)\s*[:#-]?\s*([^\n.;]+)", answer, re.I)
    return max(1, len(matches)) if matches else 0


def version_metrics(source_version_ids: list[int], expected_version_ids: Iterable[int]) -> tuple[float, float]:
    expected = set(expected_version_ids)
    actual = set(source_version_ids)
    if not expected:
        return 1.0, 1.0
    precision = len(actual & expected) / len(actual) if actual else 0.0
    recall = len(actual & expected) / len(expected)
    return precision, recall


def faithfulness_score(answer: str | None, expected_keywords: list[str]) -> float:
    """Proxy déterministe : couverture des faits attendus.
    Un vrai juge sémantique peut remplacer cette fonction sans changer le contrat."""
    return keyword_coverage(answer, expected_keywords)


def answer_relevance_score(answer: str | None, expected_keywords: list[str]) -> float:
    return keyword_coverage(answer, expected_keywords)


def hallucination_rate(answer: str | None, expected_keywords: list[str]) -> float:
    if not answer:
        return 0.0
    # Proxy conservateur : manque de couverture des faits attendus, pas preuve de hallucination.
    return 1.0 - keyword_coverage(answer, expected_keywords)
