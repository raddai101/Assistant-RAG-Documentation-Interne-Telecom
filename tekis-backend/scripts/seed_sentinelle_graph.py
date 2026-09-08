"""Peuple la chaîne de vérité terrain Sentinelle 5G dans Neo4j."""
from app import create_app
from app.models.chunk import Chunk
from app.extensions import db
from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService


def chunk_ids(*terms: str) -> list[int]:
    rows = Chunk.query.all()
    return [row.id for row in rows if any(term.lower() in row.content.lower() for term in terms)]


def main() -> None:
    app = create_app("development")
    with app.app_context():
        graph = GraphService(Neo4jGraphStore(app.config["NEO4J_URI"], app.config["NEO4J_USER"], app.config["NEO4J_PASSWORD"]))
        capex = chunk_ids("Sentinelle", "Konga Systems", "dépassement budgétaire")
        contract = chunk_ids("CTR-2025-0142", "48h", "Bomoko Telecom")
        sites = chunk_ids("LUB-GNB-001", "KIN-GNB-001", "registre des sites")
        incident = chunk_ids("INC-2026-0231", "9h", "début avril 2026")
        all_sources = sorted(set(capex + contract + sites + incident))

        entities = [
            GraphEntity("project:sentinelle-5g", "PROJECT", "Projet Sentinelle 5G", {"year": 2026}, capex),
            GraphEntity("supplier:konga-systems", "SUPPLIER", "Konga Systems", {}, sorted(set(capex + contract + incident))),
            GraphEntity("contract:ctr-2025-0142", "CONTRACT", "CTR-2025-0142", {"sla_intervention": "48h", "partner": "Bomoko Telecom"}, contract),
            GraphEntity("site:lub-gnb-001", "SITE", "LUB-GNB-001", {"status": "deployment"}, sites),
            GraphEntity("site:kin-gnb-001", "SITE", "KIN-GNB-001", {"status": "in_service"}, sites + incident),
            GraphEntity("incident:inc-2026-0231", "INCIDENT", "INC-2026-0231", {"date": "début avril 2026", "actual_intervention": "9h"}, incident),
            GraphEntity("company:bomoko-telecom", "COMPANY", "Bomoko Telecom", {}, contract),
        ]
        for entity in entities:
            graph.upsert_entity(entity)

        relationships = [
            GraphRelationship("project:sentinelle-5g", "supplier:konga-systems", "BUDGET_OVERRUN_LINKED_TO", {"year": 2026}, capex),
            GraphRelationship("supplier:konga-systems", "contract:ctr-2025-0142", "BOUND_BY", {"sla_intervention": "48h", "partner": "Bomoko Telecom"}, contract),
            GraphRelationship("contract:ctr-2025-0142", "site:lub-gnb-001", "COVERS", {"purpose": "deployment"}, sites),
            GraphRelationship("contract:ctr-2025-0142", "site:kin-gnb-001", "COVERS", {"purpose": "in_service"}, sites),
            GraphRelationship("incident:inc-2026-0231", "site:kin-gnb-001", "AFFECTS", {"date": "début avril 2026"}, incident),
            GraphRelationship("incident:inc-2026-0231", "supplier:konga-systems", "ASSIGNED_TO", {"actual_intervention": "9h"}, incident),
            GraphRelationship("contract:ctr-2025-0142", "company:bomoko-telecom", "LINKED_TO", {"sla_intervention": "48h"}, contract),
        ]
        for relationship in relationships:
            graph.upsert_relationship(relationship)
        print(f"source_chunks={len(all_sources)} entities={len(entities)} relationships={len(relationships)}")


if __name__ == "__main__":
    main()
