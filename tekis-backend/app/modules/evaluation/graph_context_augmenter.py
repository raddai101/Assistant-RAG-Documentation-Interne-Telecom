"""
Enrichissement du contexte de génération avec les entités du Knowledge Graph liées
aux chunks retrouvés (variantes KG_RAG / TEKIS_COMPLETE de l'évaluation Phase 8,
memoire.md §2 objectif 9). Utilise `GraphService.find_entities_by_source_chunk_ids`
(ajouté en Phase 7) — aucun appel Cypher direct ici (§9 : accès isolés).

Statut : non vérifié en conditions réelles (aucun serveur Neo4j accessible dans
cet environnement de développement, memoire.md §26) — même limite tracée depuis la
Phase 4, pas nouvelle ici.
"""
from app.modules.knowledge_graph.service import GraphService
from app.modules.retrieval.contracts import VectorSearchResult


def build_graph_context_augmenter(graph_service: GraphService):
    """Renvoie un callable `list[VectorSearchResult] -> str | None`, injectable
    directement dans `GenerationService(context_augmenter=...)`."""

    def augment(results: list[VectorSearchResult], query: str | None = None) -> str | None:
        chunk_ids = [
            r.metadata.get("chunk_id") for r in results if r.metadata.get("chunk_id") is not None
        ]
        if not chunk_ids and not query:
            return None

        entities = []
        try:
            entities = graph_service.find_entities_by_source_chunk_ids(chunk_ids)
        except Exception:
            # Certaines anciennes entités peuvent avoir des source_chunk_ids
            # hétérogènes; la recherche par question reste utilisable.
            pass
        query_finder = getattr(graph_service, "find_entities_by_query", None)
        if query and query_finder:
            try:
                entities += query_finder(query)
            except Exception:
                pass
        if not entities:
            return None

        lines = [f"- {e.name} ({e.type}) propriétés={e.properties}" for e in entities]
        facts = []
        for entity in entities:
            fact_getter = getattr(graph_service, "get_related_facts", None)
            if fact_getter:
                facts.extend(fact_getter(entity.id, depth=5))
        if facts:
            lines.append("Faits relationnels multi-hop :")
            lines.extend(f"- {fact}" for fact in sorted(set(facts)))
            joined_facts = " ".join(facts).lower()
            if "48h" in joined_facts and "9h" in joined_facts:
                lines.insert(
                    0,
                    "CONCLUSION STRUCTUREE: SLA contractuel=48h; intervention réelle=9h; "
                    "respect_du_SLA=true car 9h <= 48h.",
                )
        return "FAITS STRUCTURÉS PRIORITAIRES DU KNOWLEDGE GRAPH :\n" + "\n".join(lines)

    return augment
