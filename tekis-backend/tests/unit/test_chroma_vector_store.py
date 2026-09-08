from app.modules.retrieval.contracts import VectorRecord
from app.modules.retrieval.vector.chroma_store import ChromaVectorStore


def _store(tmp_path):
    return ChromaVectorStore(
        persist_dir=str(tmp_path / "chroma"), collection_name="test_collection"
    )


def test_upsert_and_search_returns_closest_vector(tmp_path):
    store = _store(tmp_path)
    store.upsert(
        [
            VectorRecord(id="a", embedding=[1.0, 0.0], document="doc A", metadata={"chunk_id": 1}),
            VectorRecord(id="b", embedding=[0.0, 1.0], document="doc B", metadata={"chunk_id": 2}),
        ]
    )

    results = store.search(query_embedding=[0.9, 0.1], top_k=1)

    assert len(results) == 1
    assert results[0].id == "a"
    assert results[0].document == "doc A"
    assert results[0].metadata["chunk_id"] == 1


def test_get_returns_stored_records(tmp_path):
    store = _store(tmp_path)
    store.upsert([VectorRecord(id="x", embedding=[1.0, 2.0], document="contenu", metadata={"k": "v"})])

    records = store.get(["x"])

    assert len(records) == 1
    assert records[0].document == "contenu"
    assert records[0].metadata == {"k": "v"}


def test_delete_removes_vector(tmp_path):
    store = _store(tmp_path)
    store.upsert([VectorRecord(id="x", embedding=[1.0, 0.0], document="a supprimer", metadata={})])

    store.delete(["x"])

    assert store.get(["x"]) == []


def test_health_returns_true_when_reachable(tmp_path):
    store = _store(tmp_path)
    assert store.health() is True


def test_upsert_empty_list_is_noop(tmp_path):
    store = _store(tmp_path)
    store.upsert([])  # ne doit pas lever d'exception


def test_search_with_where_filter_restricts_results(tmp_path):
    """Phase 5 : le filtrage par métadonnées (ACL/temporel) doit être appliqué par
    ChromaDB lui-même, pas par un post-filtrage côté Python après coup (§15)."""
    store = _store(tmp_path)
    store.upsert(
        [
            VectorRecord(id="a", embedding=[1.0, 0.0], document="doc A", metadata={"document_version_id": 1}),
            VectorRecord(id="b", embedding=[1.0, 0.0], document="doc B", metadata={"document_version_id": 2}),
        ]
    )

    results = store.search(
        query_embedding=[1.0, 0.0], top_k=5, where={"document_version_id": {"$in": [2]}}
    )

    assert len(results) == 1
    assert results[0].id == "b"
