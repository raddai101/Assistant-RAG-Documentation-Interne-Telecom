import os
import sys

sys.path.insert(0, "/app")

from app import create_app
from app.extensions import db
from app.models.chunk import Chunk
from app.modules.generation.ollama_client import OllamaEmbeddingClient
from app.modules.retrieval.chroma_store import ChromaVectorStore
from app.modules.retrieval.contracts import VectorRecord

NEW_COLLECTION = "tekis_enterprise_kb_rebuild_20260911"

app = create_app("development")

with app.app_context():
    chunks = (
        db.session.query(Chunk)
        .order_by(Chunk.id)
        .all()
    )

    print(f"Chunks trouvés dans PostgreSQL : {len(chunks)}")

    if len(chunks) != 337:
        raise RuntimeError(
            f"ATTENTION : {len(chunks)} chunks trouvés, 337 attendus."
        )

    embedding_client = OllamaEmbeddingClient(
        base_url=os.environ["OLLAMA_BASE_URL"],
        model=os.environ["OLLAMA_EMBEDDING_MODEL"],
        timeout=300,
    )

    vector_store = ChromaVectorStore(
        persist_dir=os.environ["CHROMA_PERSIST_DIR"],
        collection_name=NEW_COLLECTION,
    )

    print(f"Nouvelle collection Chroma : {NEW_COLLECTION}")
    print("Aucune donnée PostgreSQL ne sera modifiée.")
    print()

    batch_size = 16
    total = 0

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        texts = [chunk.content for chunk in batch]

        first_id = batch[0].id
        last_id = batch[-1].id

        print(
            f"[{start + 1}-{start + len(batch)}/337] "
            f"Embedding chunks {first_id}-{last_id}...",
            flush=True,
        )

        vectors = embedding_client.embed_batch(texts)

        if len(vectors) != len(batch):
            raise RuntimeError(
                f"Ollama a retourné {len(vectors)} vecteurs "
                f"pour {len(batch)} chunks."
            )

        records = []

        for chunk, vector in zip(batch, vectors):
            if len(vector) != 1024:
                raise RuntimeError(
                    f"Dimension invalide pour chunk-{chunk.id}: "
                    f"{len(vector)} au lieu de 1024."
                )

            records.append(
                VectorRecord(
                    id=f"chunk-{chunk.id}",
                    embedding=vector,
                    document=chunk.content,
                    metadata={
                        "chunk_id": chunk.id,
                        "document_version_id": chunk.document_version_id,
                        "page": chunk.page,
                        "section": chunk.section,
                    },
                )
            )

        vector_store.upsert(records)

        total += len(records)
        print(f"    OK → {total}/337", flush=True)

    count = vector_store._collection.count()

    print()
    print("========================================")
    print("VÉRIFICATION FINALE")
    print("========================================")
    print(f"Collection : {NEW_COLLECTION}")
    print(f"Vecteurs   : {count}")

    if count != 337:
        raise RuntimeError(
            f"ÉCHEC : Chroma contient {count} vecteurs au lieu de 337."
        )

    # Vérification des IDs
    result = vector_store._collection.get(
        ids=["chunk-1", "chunk-2", "chunk-337"],
        include=["metadatas"],
    )

    ids = result.get("ids", [])

    print(f"IDs testés : {ids}")

    expected = {"chunk-1", "chunk-2", "chunk-337"}

    if set(ids) != expected:
        raise RuntimeError(
            f"IDs Chroma incorrects : {ids}"
        )

    print()
    print("SUCCESS")
    print("337/337 chunks ont été indexés dans la nouvelle collection.")
    print("PostgreSQL n'a pas été modifié.")
