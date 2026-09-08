"""
Blueprint `embeddings` — route HTTP pure (§9). Endpoint opérationnel ajouté en
Phase 2, non présent dans la liste initiale de §7 (memoire.md) : nécessaire pour
déclencher l'indexation vectorielle des chunks déjà ingérés en Phase 1. Signalé et
documenté ici plutôt qu'ajouté silencieusement (§3 des instructions).
"""
from flask import Blueprint, request, jsonify, current_app

from app.modules.generation.ollama_client import OllamaEmbeddingClient, OllamaError
from app.modules.retrieval.vector.chroma_store import ChromaVectorStore
from app.modules.retrieval.indexing_service import EmbeddingIndexingService

embeddings_bp = Blueprint("embeddings", __name__)


def _build_indexing_service(app_config) -> EmbeddingIndexingService:
    embedding_client = OllamaEmbeddingClient(
        base_url=app_config["OLLAMA_BASE_URL"],
        model=app_config["OLLAMA_EMBEDDING_MODEL"],
    )
    vector_store = ChromaVectorStore(
        persist_dir=app_config["CHROMA_PERSIST_DIR"],
        collection_name=app_config["CHROMA_COLLECTION_NAME"],
    )
    return EmbeddingIndexingService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        embedding_model_name=app_config["OLLAMA_EMBEDDING_MODEL"],
    )


@embeddings_bp.post("/reindex")
def reindex_embeddings():
    document_version_id = request.get_json(silent=True) or {}
    document_version_id = document_version_id.get("document_version_id")

    service = _build_indexing_service(current_app.config)
    try:
        result = service.index_pending_chunks(document_version_id=document_version_id)
    except OllamaError as e:
        return (
            jsonify({"success": False, "data": None, "message": None, "error": str(e)}),
            503,
        )

    return jsonify(
        {
            "success": True,
            "data": {"num_chunks_indexed": result.num_chunks_indexed},
            "message": "Indexation terminée.",
            "error": None,
        }
    )
