"""
Analyse d'impact (memoire.md §15) : à partir des chunks modifiés/supprimés d'une
comparaison de versions, retrouve dans le Knowledge Graph (Phase 4) les entités
directement liées (équipes, procédures, projets, etc. via `source_chunk_ids`) puis
leurs entités liées de proche en proche (impact indirect).

Dépend de `GraphService` (module `knowledge_graph`), pas directement de Neo4j —
cohérent avec §9 et le principe d'isolation déjà appliqué au reste du projet.
"""
from app.modules.change_intelligence.contracts import ImpactedEntity, ImpactAnalysisResult
from app.modules.knowledge_graph.service import GraphService

DEFAULT_INDIRECT_DEPTH = 1


class ImpactAnalysisService:
    def __init__(self, graph_service: GraphService):
        self._graph_service = graph_service

    def analyze(self, affected_chunk_ids: list[int], indirect_depth: int = DEFAULT_INDIRECT_DEPTH) -> ImpactAnalysisResult:
        if not affected_chunk_ids:
            return ImpactAnalysisResult()

        direct_entities = self._graph_service.find_entities_by_source_chunk_ids(affected_chunk_ids)
        direct_ids = {e.id for e in direct_entities}

        directly_linked = [
            ImpactedEntity(
                entity_id=e.id,
                type=e.type,
                name=e.name,
                via_chunk_ids=[cid for cid in e.source_chunk_ids if cid in affected_chunk_ids],
            )
            for e in direct_entities
        ]

        # Impact indirect : entités liées aux entités directement impactées, sans
        # dupliquer celles déjà listées comme directement impactées (§18 : le
        # graphe complète, ne remplace pas — on distingue explicitement direct vs
        # indirect plutôt que de tout fusionner dans une seule liste opaque).
        indirect_by_id: dict[str, ImpactedEntity] = {}
        for entity in direct_entities:
            related = self._graph_service.get_related_entities(entity.id, depth=indirect_depth)
            for r in related:
                if r.id in direct_ids or r.id == entity.id:
                    continue
                if r.id not in indirect_by_id:
                    indirect_by_id[r.id] = ImpactedEntity(entity_id=r.id, type=r.type, name=r.name, via_chunk_ids=[])

        return ImpactAnalysisResult(
            directly_linked_entities=directly_linked,
            indirectly_related_entities=list(indirect_by_id.values()),
        )
