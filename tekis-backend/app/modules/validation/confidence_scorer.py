"""
Score de confiance (module `validation`, Phase 6, memoire.md §14).

Hypothèse explicite, à vérifier par Radda101 (même limite que les Phases 2-4, aucun
reranker réel disponible dans cet environnement pour la calibrer) : le champ
`distance` de `VectorSearchResult` porte le score du reranker cross-encoder
(`BAAI/bge-reranker-v2-m3` via `HybridRetrievalService`, memoire.md §24), pas une
distance vectorielle brute. Un cross-encoder de ce type produit un logit non borné ;
la sigmoïde le ramène dans `[0, 1]` pour en faire une confiance interprétable — c'est
une approximation raisonnable, pas une calibration mesurée sur données réelles.
"""
import math

from app.modules.retrieval.contracts import VectorSearchResult


class ConfidenceScorer:
    def score(self, results: list[VectorSearchResult]) -> float:
        if not results:
            return 0.0
        top_score = results[0].distance
        if top_score is None:
            # Le retrieval sous-jacent n'a pas fourni de score exploitable (ex.
            # RetrievalService Phase 2 pur, distance vectorielle non calibrée) :
            # on ne peut pas honnêtement quantifier une confiance ici.
            return 0.0
        return 1.0 / (1.0 + math.exp(-top_score))
