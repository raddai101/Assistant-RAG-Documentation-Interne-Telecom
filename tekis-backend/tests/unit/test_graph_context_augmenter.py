from app.modules.evaluation.graph_context_augmenter import build_graph_context_augmenter
from app.modules.knowledge_graph.contracts import GraphEntity
from app.modules.retrieval.contracts import VectorSearchResult


class FakeGraphService:
    def __init__(self, entities_by_chunk):
        self._entities_by_chunk = entities_by_chunk

    def find_entities_by_source_chunk_ids(self, chunk_ids):
        seen = {}
        for cid in chunk_ids:
            for entity in self._entities_by_chunk.get(cid, []):
                seen[entity.id] = entity
        return list(seen.values())


def _result(chunk_id):
    return VectorSearchResult(id=f"chunk-{chunk_id}", document="contenu", metadata={"chunk_id": chunk_id}, distance=0.1)


def test_augmenter_returns_none_when_no_chunk_ids():
    augment = build_graph_context_augmenter(FakeGraphService({}))
    assert augment([]) is None


def test_augmenter_returns_none_when_no_linked_entities():
    augment = build_graph_context_augmenter(FakeGraphService({}))
    assert augment([_result(1)]) is None


def test_augmenter_includes_entity_name_and_type():
    entity = GraphEntity(id="proc:1", type="Procedure", name="Maintenance SGSN", source_chunk_ids=[1])
    augment = build_graph_context_augmenter(FakeGraphService({1: [entity]}))

    context = augment([_result(1)])

    assert "Maintenance SGSN" in context
    assert "Procedure" in context


def test_augmenter_deduplicates_entities_across_chunks():
    entity = GraphEntity(id="proc:1", type="Procedure", name="Maintenance SGSN", source_chunk_ids=[1, 2])
    augment = build_graph_context_augmenter(FakeGraphService({1: [entity], 2: [entity]}))

    context = augment([_result(1), _result(2)])

    assert context.count("Maintenance SGSN") == 1
