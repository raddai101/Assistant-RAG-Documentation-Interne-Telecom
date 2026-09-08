"""Extrait et persiste les relations métier des chunks documentaires dans Neo4j."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models.chunk import Chunk
from app.modules.generation.ollama_client import OllamaLLMClient
from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService

ENTITY_TYPES = {"PROJECT", "SUPPLIER", "CONTRACT", "SITE", "INCIDENT", "DOCUMENT", "DEPARTMENT"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9_]+$")


def parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def normalize_type(value: str) -> str:
    value = str(value or "DOCUMENT").upper().replace(" ", "_")
    return value if value in ENTITY_TYPES else "DOCUMENT"


def safe_relation(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", str(value or "RELATED_TO").upper())
    return value or "RELATED_TO"


def extract_graph(llm, chunk_id: int, content: str) -> dict:
    prompt = f"""Extrais uniquement les faits explicites du texte télécom suivant pour un graphe de connaissances.
Retourne uniquement un JSON valide de la forme:
{{"entities":[{{"id":"stable_id","type":"PROJECT|SUPPLIER|CONTRACT|SITE|INCIDENT|DOCUMENT|DEPARTMENT","name":"nom","properties":{{}}}}],"relationships":[{{"source_id":"id","target_id":"id","type":"RELATION_IN_UPPER_SNAKE_CASE","properties":{{}}}}]}}
Les identifiants doivent être stables et lisibles. N'invente aucun fait absent du texte.
Associe chaque entité et relation à la source chunk {chunk_id}.
TEXTE:
{content}"""
    return parse_json_object(llm.generate(prompt))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contains", nargs="+", default=["Sentinelle", "Konga", "CTR-2025-0142", "KIN-GNB-001", "INC-2026-0231", "Bomoko"])
    args = parser.parse_args()
    app = create_app("development")
    with app.app_context():
        llm = OllamaLLMClient(
            app.config["OLLAMA_BASE_URL"],
            app.config["OLLAMA_LLM_MODEL"],
            temperature=0.0,
            top_p=0.9,
            top_k=40,
        )
        graph = GraphService(Neo4jGraphStore(app.config["NEO4J_URI"], app.config["NEO4J_USER"], app.config["NEO4J_PASSWORD"]))
        terms = [term.lower() for term in args.contains]
        chunks = Chunk.query.order_by(Chunk.id).all()
        selected = [chunk for chunk in chunks if any(term in chunk.content.lower() for term in terms)]
        entity_count = relationship_count = 0
        for chunk in selected:
            extracted = extract_graph(llm, chunk.id, chunk.content)
            entities = {}
            for raw in extracted.get("entities", []):
                entity_id = str(raw.get("id", "")).strip()
                name = str(raw.get("name", "")).strip()
                if not entity_id or not name or not TOKEN_RE.match(entity_id):
                    continue
                entity = GraphEntity(entity_id, normalize_type(raw.get("type")), name, raw.get("properties") or {}, [chunk.id])
                graph.upsert_entity(entity)
                entities[entity_id] = entity
                entity_count += 1
            for raw in extracted.get("relationships", []):
                source_id = str(raw.get("source_id", "")).strip()
                target_id = str(raw.get("target_id", "")).strip()
                if source_id not in entities or target_id not in entities:
                    continue
                graph.upsert_relationship(GraphRelationship(source_id, target_id, safe_relation(raw.get("type")), raw.get("properties") or {}, [chunk.id]))
                relationship_count += 1
        print(f"chunks_examined={len(selected)} entities_upserted={entity_count} relationships_upserted={relationship_count}")


if __name__ == "__main__":
    main()
