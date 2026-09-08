"""
Implémentation du `RerankerContract` avec le cross-encoder `BAAI/bge-reranker-v2-m3`
(memoire.md §17 décision #11), via la librairie `sentence-transformers`.

Chargement paresseux : le modèle n'est importé/instancié qu'au premier appel réel de
`rerank()`, pas à la construction de l'objet. Le téléchargement des poids depuis
Hugging Face Hub (~1,1 Go la première fois) ne doit bloquer ni le démarrage de
l'application, ni les tests qui n'exercent pas réellement le reranker.

**Non testé en conditions réelles dans cet environnement de développement** : pas
d'accès réseau à `huggingface.co` depuis ce sandbox (domaines réseau autorisés listés
en tête de session). Même limite que les clients Ollama en Phase 2 (memoire.md §23) —
tracée par avance en §24 plutôt que découverte en fin de phase. Voir
`tests/unit/test_reranker.py` pour les tests basés sur un modèle factice injecté.
"""
from app.modules.retrieval.reranker.contracts import RerankCandidate, RerankedResult


class CrossEncoderReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        self._model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            # Import paresseux : évite de tirer torch/transformers au démarrage de
            # l'app si le reranker n'est jamais sollicité (ex. tests qui n'exercent
            # que le retrieval vectoriel ou lexical seul).
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        return self._model

    def rerank(
        self, query: str, candidates: list[RerankCandidate], top_k: int
    ) -> list[RerankedResult]:
        if not candidates:
            return []

        model = self._load_model()
        pairs = [(query, c.content) for c in candidates]
        scores = model.predict(pairs)

        reranked = [
            RerankedResult(chunk_id=c.chunk_id, content=c.content, metadata=c.metadata, score=float(s))
            for c, s in zip(candidates, scores)
        ]
        reranked.sort(key=lambda r: r.score, reverse=True)
        return reranked[:top_k]
