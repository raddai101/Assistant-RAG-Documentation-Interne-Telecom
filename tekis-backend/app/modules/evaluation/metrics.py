"""
Métriques d'évaluation (Phase 8, memoire.md §2 objectif 9). Fonctions pures, sans
dépendance DB/réseau — testables indépendamment de toute infrastructure, cohérent
avec la stratégie de tests du projet (§16 : jamais de données réelles confidentielles,
donc l'évaluation elle-même doit pouvoir tourner sur un corpus synthétique).

**Portée assumée, à ne pas surinterpréter** : les métriques de « grounding » et
« hallucination » implémentées ici (`keyword_coverage`) sont des **proxys lexicaux
simples** (couverture de mots-clés attendus dans la réponse), pas une évaluation
sémantique par un juge LLM. Une évaluation plus fine nécessiterait un juge LLM dédié
et un corpus de référence annoté — hors périmètre de cette livraison, signalé ici
plutôt que développé spontanément (§3 des instructions : ne pas anticiper une
fonctionnalité non demandée).
"""


def precision_at_k(retrieved_ids: list[int], relevant_ids: set[int], k: int) -> float:
    """Retrieval — fraction des k premiers résultats retournés qui sont pertinents."""
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for cid in top_k if cid in relevant_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: list[int], relevant_ids: set[int], k: int) -> float:
    """Retrieval — fraction des chunks pertinents effectivement retrouvés dans le
    top-k. 0.0 si aucun chunk pertinent n'était attendu (question mal définie)."""
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for cid in top_k if cid in relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[int], relevant_ids: set[int]) -> float:
    """Retrieval — 1/rang du premier résultat pertinent (0.0 si aucun)."""
    for rank, cid in enumerate(retrieved_ids, start=1):
        if cid in relevant_ids:
            return 1.0 / rank
    return 0.0


def keyword_coverage(answer: str | None, expected_keywords: list[str]) -> float:
    """Proxy de grounding/hallucination : fraction des mots-clés attendus présents
    dans la réponse (insensible à la casse). Ne prouve pas la véracité factuelle —
    seulement la présence lexicale des faits attendus."""
    if not expected_keywords:
        return 1.0  # rien n'était attendu -> trivialement "couvert"
    if not answer:
        return 0.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer_lower)
    return hits / len(expected_keywords)


def abstention_correctness(expected_abstain: bool, actual_abstained: bool) -> bool:
    """Abstention — la décision d'abstenir (ou non) était-elle la bonne ?"""
    return expected_abstain == actual_abstained


def acl_leak_count(source_document_version_ids: list[int], forbidden_version_ids: set[int]) -> int:
    """Sécurité — nombre de sources renvoyées appartenant à une version de document
    interdite pour l'utilisateur. Doit toujours valoir 0 : un document interdit ne
    doit jamais atteindre le contexte du LLM (§17/§15 des instructions permanentes)."""
    if not forbidden_version_ids:
        return 0
    return sum(1 for vid in source_document_version_ids if vid in forbidden_version_ids)
