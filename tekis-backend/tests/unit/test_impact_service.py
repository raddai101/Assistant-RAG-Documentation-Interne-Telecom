from app.modules.change_intelligence.impact_service import ImpactAnalysisService
from app.modules.knowledge_graph.contracts import GraphEntity


class FakeGraphService:
    def __init__(self, entities_by_chunk: dict[int, list[GraphEntity]], related_by_id: dict[str, list[GraphEntity]]):
        self._entities_by_chunk = entities_by_chunk
        self._related_by_id = related_by_id

    def find_entities_by_source_chunk_ids(self, chunk_ids):
        seen = {}
        for cid in chunk_ids:
            for entity in self._entities_by_chunk.get(cid, []):
                seen[entity.id] = entity
        return list(seen.values())

    def get_related_entities(self, entity_id, relationship_type=None, depth=1):
        return self._related_by_id.get(entity_id, [])


def test_analyze_returns_empty_result_for_no_affected_chunks():
    service = ImpactAnalysisService(FakeGraphService({}, {}))

    result = service.analyze([])

    assert result.directly_linked_entities == []
    assert result.indirectly_related_entities == []


def test_analyze_finds_directly_linked_entities():
    procedure = GraphEntity(id="proc:1", type="Procedure", name="Maintenance SGSN", source_chunk_ids=[42])
    graph_service = FakeGraphService(entities_by_chunk={42: [procedure]}, related_by_id={})

    service = ImpactAnalysisService(graph_service)
    result = service.analyze([42])

    assert len(result.directly_linked_entities) == 1
    assert result.directly_linked_entities[0].entity_id == "proc:1"
    assert result.directly_linked_entities[0].via_chunk_ids == [42]


def test_analyze_finds_indirectly_related_entities():
    procedure = GraphEntity(id="proc:1", type="Procedure", name="Maintenance SGSN", source_chunk_ids=[42])
    team = GraphEntity(id="team:reseau", type="Department", name="Équipe Réseau")

    graph_service = FakeGraphService(
        entities_by_chunk={42: [procedure]},
        related_by_id={"proc:1": [team]},
    )

    service = ImpactAnalysisService(graph_service)
    result = service.analyze([42])

    assert len(result.indirectly_related_entities) == 1
    assert result.indirectly_related_entities[0].entity_id == "team:reseau"


def test_analyze_does_not_duplicate_direct_entity_in_indirect_list():
    procedure = GraphEntity(id="proc:1", type="Procedure", name="Maintenance SGSN", source_chunk_ids=[42])
    other_procedure = GraphEntity(id="proc:2", type="Procedure", name="Autre procédure", source_chunk_ids=[43])

    graph_service = FakeGraphService(
        entities_by_chunk={42: [procedure], 43: [other_procedure]},
        # proc:1 est lié à proc:2, qui est LUI-MÊME dans la liste des directs
        related_by_id={"proc:1": [other_procedure]},
    )

    service = ImpactAnalysisService(graph_service)
    result = service.analyze([42, 43])

    direct_ids = {e.entity_id for e in result.directly_linked_entities}
    indirect_ids = {e.entity_id for e in result.indirectly_related_entities}
    assert "proc:2" in direct_ids
    assert "proc:2" not in indirect_ids
