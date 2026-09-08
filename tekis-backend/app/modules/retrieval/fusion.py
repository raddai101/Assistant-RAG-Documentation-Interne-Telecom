"""
Fusion des résultats de recherche lexicale et vectorielle par Reciprocal Rank Fusion
(RRF) — méthode standard pour combiner des classements hétérogènes sans avoir à
normaliser des scores de nature différente (distance cosinus ChromaDB vs `ts_rank`
PostgreSQL, qui ne sont pas comparables directement). Référence : Cormack, Clarke &
Buettcher, « Reciprocal Rank Fusion outperforms Condorcet and individual Rank
Learning Methods », SIGIR 2009.

RRF_K = 60 : constante usuelle de la littérature (atténue le poids des tout premiers
rangs pour éviter qu'une seule liste domine totalement la fusion). Valeur à ajuster
en Phase 8 (Évaluation) si les métriques sur corpus réel le justifient — non modifiée
sans données pour argumenter le changement.
"""
from dataclasses import dataclass, field

RRF_K = 60


@dataclass
class FusedCandidate:
    chunk_id: int
    content: str
    metadata: dict = field(default_factory=dict)
    fused_score: float = 0.0


def reciprocal_rank_fusion(
    vector_ranked: list[tuple[int, str, dict]],
    lexical_ranked: list[tuple[int, str, dict]],
    k: int = RRF_K,
) -> list[FusedCandidate]:
    """
    `vector_ranked` et `lexical_ranked` : listes de `(chunk_id, content, metadata)`
    déjà triées par pertinence décroissante (meilleur résultat en premier). Renvoie
    la liste fusionnée, triée par score RRF décroissant.
    """
    scores: dict[int, float] = {}
    content_by_id: dict[int, str] = {}
    metadata_by_id: dict[int, dict] = {}

    for source in (vector_ranked, lexical_ranked):
        for rank, (chunk_id, content, metadata) in enumerate(source, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            content_by_id.setdefault(chunk_id, content)
            metadata_by_id.setdefault(chunk_id, metadata)

    fused = [
        FusedCandidate(
            chunk_id=chunk_id,
            content=content_by_id[chunk_id],
            metadata=metadata_by_id[chunk_id],
            fused_score=score,
        )
        for chunk_id, score in scores.items()
    ]
    fused.sort(key=lambda c: c.fused_score, reverse=True)
    return fused
