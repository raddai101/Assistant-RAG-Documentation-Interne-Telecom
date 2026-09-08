"""
Clients HTTP vers Ollama (exécution locale, memoire.md §4 décision #8 : Qwen3-14B +
BGE-M3 via Ollama, aucun appel réseau externe pour respecter la confidentialité des
documents télécom).

Choix technique : `urllib.request` (stdlib) plutôt que la librairie `requests`. Deux
appels HTTP JSON simples ne justifient pas une dépendance supplémentaire (§10 des
instructions) — même logique que le choix `zipfile` plutôt que `python-magic` en
Phase 1 (memoire.md §19).
"""
import json
import urllib.error
import urllib.request


class OllamaError(RuntimeError):
    """Levée quand Ollama est injoignable ou renvoie une réponse invalide."""


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise OllamaError(f"Ollama injoignable sur {url} : {e}") from e
    except json.JSONDecodeError as e:
        raise OllamaError(f"Réponse Ollama invalide (JSON attendu) depuis {url}") from e


class OllamaEmbeddingClient:
    """Implémente `EmbeddingClient` via l'endpoint `/api/embeddings` d'Ollama."""

    def __init__(self, base_url: str, model: str, timeout: int = 300):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            try:
                body = _post_json(
                    f"{self._base_url}/api/embeddings",
                    {"model": self._model, "prompt": text},
                    self._timeout,
                )
            except OllamaError:
                return self.embed_batch(texts)
            if "embedding" not in body:
                return self.embed_batch(texts)
            vectors.append(body["embedding"])
        return vectors

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        batch_size = 16
        all_vectors: list[list[float]] = []

        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]

            body = _post_json(
                f"{self._base_url}/api/embed",
                {"model": self._model, "input": batch},
                self._timeout,
            )

            vectors = body.get("embeddings")

            if not isinstance(vectors, list) or len(vectors) != len(batch):
                raise OllamaError(
                    f"Réponse Ollama sans embeddings batch valides pour le modèle "
                    f"{self._model}."
                )

            all_vectors.extend(vectors)

        return all_vectors

class OllamaLLMClient:
    """Implémente `LLMClient` via l'endpoint `/api/generate` d'Ollama."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 300,
        temperature: float = 0.15,
        top_p: float = 0.9,
        top_k: int = 40,
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._options = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
        }

    def generate(self, prompt: str) -> str:
        body = _post_json(
            f"{self._base_url}/api/generate",
            {"model": self._model, "prompt": prompt, "stream": False, "options": self._options},
            self._timeout,
        )
        if "response" not in body:
            raise OllamaError(
                f"Réponse Ollama sans champ 'response' pour le modèle {self._model}."
            )
        return body["response"]
