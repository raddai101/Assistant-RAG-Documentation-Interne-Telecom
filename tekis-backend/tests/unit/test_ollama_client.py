"""
Ce sandbox n'a pas accès réseau à un serveur Ollama réel (ni au sens propre :
`localhost:11434` n'existe pas ici ; ni à cause des règles réseau de l'environnement).
Les appels HTTP sont donc mockés au niveau `urllib.request.urlopen`, ce qui suffit à
vérifier la construction des requêtes et le parsing des réponses — la vérification
avec un Ollama réel reste à faire par Radda101 sur son infrastructure.
"""
import json
from unittest.mock import patch, MagicMock

import pytest

from app.modules.generation.ollama_client import (
    OllamaEmbeddingClient,
    OllamaLLMClient,
    OllamaError,
)


def _fake_response(payload: dict):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    return mock_resp


@patch("app.modules.generation.ollama_client.urllib.request.urlopen")
def test_embedding_client_calls_correct_endpoint_and_parses_vector(mock_urlopen):
    mock_urlopen.return_value = _fake_response({"embedding": [0.1, 0.2, 0.3]})
    client = OllamaEmbeddingClient(base_url="http://localhost:11434", model="bge-m3")

    vectors = client.embed(["texte de test"])

    assert vectors == [[0.1, 0.2, 0.3]]
    called_request = mock_urlopen.call_args[0][0]
    assert called_request.full_url == "http://localhost:11434/api/embeddings"
    sent_body = json.loads(called_request.data.decode("utf-8"))
    assert sent_body == {"model": "bge-m3", "prompt": "texte de test"}


@patch("app.modules.generation.ollama_client.urllib.request.urlopen")
def test_embedding_client_embeds_multiple_texts_in_order(mock_urlopen):
    mock_urlopen.side_effect = [
        _fake_response({"embedding": [1.0]}),
        _fake_response({"embedding": [2.0]}),
    ]
    client = OllamaEmbeddingClient(base_url="http://localhost:11434", model="bge-m3")

    vectors = client.embed(["a", "b"])

    assert vectors == [[1.0], [2.0]]


@patch("app.modules.generation.ollama_client.urllib.request.urlopen")
def test_embedding_client_raises_ollama_error_on_missing_field(mock_urlopen):
    mock_urlopen.return_value = _fake_response({"unexpected": "shape"})
    client = OllamaEmbeddingClient(base_url="http://localhost:11434", model="bge-m3")

    with pytest.raises(OllamaError, match="embedding"):
        client.embed(["texte"])


@patch("app.modules.generation.ollama_client.urllib.request.urlopen")
def test_llm_client_calls_generate_endpoint_and_returns_text(mock_urlopen):
    mock_urlopen.return_value = _fake_response({"response": "Voici la réponse."})
    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:4b")

    text = client.generate("Quelle est la procédure SGSN ?")

    assert text == "Voici la réponse."
    called_request = mock_urlopen.call_args[0][0]
    assert called_request.full_url == "http://localhost:11434/api/generate"
    sent_body = json.loads(called_request.data.decode("utf-8"))
    assert sent_body["model"] == "qwen3:4b"
    assert sent_body["stream"] is False


@patch("app.modules.generation.ollama_client.urllib.request.urlopen")
def test_llm_client_raises_ollama_error_when_unreachable(mock_urlopen):
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("connection refused")
    client = OllamaLLMClient(base_url="http://localhost:11434", model="qwen3:4b")

    with pytest.raises(OllamaError, match="injoignable"):
        client.generate("test")
