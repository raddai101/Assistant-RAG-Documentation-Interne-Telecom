"""
Le vrai modèle `BAAI/bge-reranker-v2-m3` n'est pas chargé ici (pas d'accès réseau à
huggingface.co dans ce sandbox, memoire.md §24) : ces tests monkeypatchent
`_load_model` pour vérifier la logique de `CrossEncoderReranker.rerank()`
(construction des paires, tri par score, troncature à `top_k`) indépendamment du
modèle réellement chargé.
"""
from app.modules.retrieval.reranker.contracts import RerankCandidate
from app.modules.retrieval.reranker.cross_encoder import CrossEncoderReranker


class FakeCrossEncoderModel:
    """Simule un modèle sentence-transformers : plus le texte contient le mot-clé
    'pertinent', plus le score est élevé."""

    def predict(self, pairs):
        return [10.0 if "pertinent" in content else 1.0 for _, content in pairs]


def test_rerank_orders_candidates_by_score(monkeypatch):
    reranker = CrossEncoderReranker()
    monkeypatch.setattr(reranker, "_load_model", lambda: FakeCrossEncoderModel())

    candidates = [
        RerankCandidate(chunk_id=1, content="contenu hors sujet", metadata={}),
        RerankCandidate(chunk_id=2, content="contenu très pertinent ici", metadata={}),
    ]

    result = reranker.rerank("question", candidates, top_k=2)

    assert [r.chunk_id for r in result] == [2, 1]
    assert result[0].score == 10.0


def test_rerank_truncates_to_top_k(monkeypatch):
    reranker = CrossEncoderReranker()
    monkeypatch.setattr(reranker, "_load_model", lambda: FakeCrossEncoderModel())

    candidates = [RerankCandidate(chunk_id=i, content="contenu pertinent", metadata={}) for i in range(5)]

    result = reranker.rerank("question", candidates, top_k=2)

    assert len(result) == 2


def test_rerank_empty_candidates_returns_empty_without_loading_model():
    reranker = CrossEncoderReranker()
    # Ne monkeypatch pas _load_model : si le code tentait de charger le vrai modèle,
    # cela lèverait une ImportError (sentence-transformers non installé ici).
    result = reranker.rerank("question", [], top_k=5)
    assert result == []
