"""Construction déterministe du Knowledge Graph TEKIS à partir des chunks."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from typing import Any

from app import create_app
from app.models.chunk import Chunk
from app.modules.generation.ollama_client import OllamaLLMClient
from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService


# ---------------------------------------------------------------------------
# Ontologie autorisée
# ---------------------------------------------------------------------------

ENTITY_TYPES = {
    "PROJECT",
    "SUPPLIER",
    "CONTRACT",
    "SITE",
    "INCIDENT",
    "DOCUMENT",
    "DEPARTMENT",
    "COMPANY",
    "PERSON",
    "TECHNOLOGY",
    "PRODUCT",
    "NETWORK_ELEMENT",
}

RELATION_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


# ---------------------------------------------------------------------------
# Parsing / normalisation
# ---------------------------------------------------------------------------

def parse_json_object(text: str) -> dict[str, Any]:
    """
    Récupère un objet JSON dans une réponse LLM.

    Accepte :
    - JSON pur
    - texte entourant le JSON
    - bloc markdown ```json ... ```
    """
    if not text:
        return {}

    text = text.strip()

    # Réponse JSON pure.
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass

    # Retrait éventuel des fences markdown.
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        pass

    # Recherche du premier objet JSON englobant.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end <= start:
        return {}

    candidate = cleaned[start:end + 1]

    try:
        value = json.loads(candidate)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def normalize_text(value: Any) -> str:
    """
    Normalise un texte pour construire un identifiant stable.

    Exemple :
        "Direction Générale"
        -> "direction_generale"
    """
    text = str(value or "").strip().lower()

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")

    return text


def normalize_entity_type(value: Any) -> str:
    value = str(value or "DOCUMENT").strip().upper()

    value = re.sub(r"[\s\-]+", "_", value)

    if value in ENTITY_TYPES:
        return value

    return "DOCUMENT"


def deterministic_entity_id(entity_type: str, name: str) -> str:
    """
    Construit l'identifiant canonique d'une entité.

    L'ID ne dépend jamais du numéro du chunk ni de la position
    de l'entité dans la réponse du LLM.
    """
    normalized_type = normalize_entity_type(entity_type)
    normalized_name = normalize_text(name)

    if not normalized_name:
        normalized_name = "unknown"

    return f"{normalized_type.lower()}_{normalized_name}"


def normalize_relation(value: Any) -> str:
    """
    Transforme une relation en token Cypher sûr.
    """
    relation = str(value or "RELATED_TO").strip().upper()

    relation = unicodedata.normalize("NFKD", relation)
    relation = "".join(
        char for char in relation
        if not unicodedata.combining(char)
    )

    relation = re.sub(r"[^A-Z0-9]+", "_", relation)
    relation = re.sub(r"_+", "_", relation)
    relation = relation.strip("_")

    if not relation or not RELATION_RE.match(relation):
        return "RELATED_TO"

    return relation


def clean_properties(value: Any) -> dict[str, Any]:
    """
    Conserve uniquement des propriétés sérialisables en JSON.
    """
    if not isinstance(value, dict):
        return {}

    result: dict[str, Any] = {}

    for key, item in value.items():
        key = str(key).strip()

        if not key:
            continue

        if isinstance(item, (str, int, float, bool)) or item is None:
            result[key] = item

        elif isinstance(item, (list, dict)):
            result[key] = item

    return result


# ---------------------------------------------------------------------------
# Prompt LLM
# ---------------------------------------------------------------------------

def build_prompt(chunk_id: int, content: str) -> str:
    return f"""
Tu es un extracteur déterministe de faits pour le Knowledge Graph
d'une base documentaire interne d'une entreprise télécom.

Tu dois analyser UNIQUEMENT le texte du chunk fourni.

RÈGLES ABSOLUES :

1. N'invente aucun fait.
2. N'utilise aucune connaissance externe.
3. N'interprète pas une information absente du texte.
4. Une entité doit être explicitement identifiable dans le texte.
5. Une relation doit être explicitement justifiée par le texte.
6. Une relation ne peut relier que deux entités présentes dans "entities".
7. Les propriétés doivent provenir uniquement du texte.
8. N'utilise jamais d'identifiants comme PROJECT_1, PROJECT_2,
   DEPARTMENT_1, DEPARTMENT_2, etc.
9. L'identifiant doit être basé sur le sens de l'entité et rester stable
   entre différents chunks.
10. Conserve autant que possible le nom exact présent dans le texte.
11. Si aucune entité pertinente n'est présente, retourne une liste vide.
12. Si aucune relation explicite n'est présente, retourne une liste vide.

TYPES D'ENTITÉS AUTORISÉS :

PROJECT
SUPPLIER
CONTRACT
SITE
INCIDENT
DOCUMENT
DEPARTMENT
COMPANY
PERSON
TECHNOLOGY
PRODUCT
NETWORK_ELEMENT

TYPES DE RELATIONS :

Utilise une relation métier précise lorsque le texte la justifie,
par exemple :

MANAGED_BY
BELONGS_TO
COORDINATES_WITH
USES_TECHNOLOGY
LOCATED_IN
COVERS
AFFECTS
ASSIGNED_TO
SUPPLIES
PROVIDES
DEPENDS_ON
PART_OF
RELATED_TO
HAS_CONTRACT
BOUND_BY
LINKED_TO
DESCRIBES
OPERATES
DEPLOYED_AT

Ne crée pas une relation simplement parce que deux entités
apparaissent dans le même texte.

CHUNK SOURCE :

Le numéro du chunk est {chunk_id}.

FORMAT DE SORTIE :

Retourne UNIQUEMENT un JSON valide, sans commentaire,
sans markdown et sans texte avant ou après :

{{
  "entities": [
    {{
      "type": "PROJECT",
      "name": "Nom exact de l'entité",
      "properties": {{}}
    }}
  ],
  "relationships": [
    {{
      "source_name": "Nom exact de l'entité source",
      "source_type": "PROJECT",
      "target_name": "Nom exact de l'entité cible",
      "target_type": "SUPPLIER",
      "type": "SUPPLIES",
      "properties": {{}}
    }}
  ]
}}

IMPORTANT :

Les relations utilisent les noms et types des entités,
et NON des IDs artificiels.

Texte du chunk :

{content}
""".strip()


# ---------------------------------------------------------------------------
# Extraction LLM
# ---------------------------------------------------------------------------

def extract_graph(
    llm: OllamaLLMClient,
    chunk_id: int,
    content: str,
) -> dict[str, Any]:

    prompt = build_prompt(chunk_id, content)

    try:
        response = llm.generate(prompt)
    except Exception as exc:
        print(
            f"[ERROR] chunk={chunk_id} llm_error={exc}",
            file=sys.stderr,
            flush=True,
        )
        return {}

    return parse_json_object(response)


# ---------------------------------------------------------------------------
# Transformation extraction -> contrats GraphEntity / GraphRelationship
# ---------------------------------------------------------------------------

def process_extraction(
    extracted: dict[str, Any],
    chunk_id: int,
) -> tuple[list[GraphEntity], list[GraphRelationship]]:

    entity_by_key: dict[tuple[str, str], GraphEntity] = {}

    raw_entities = extracted.get("entities", [])

    if not isinstance(raw_entities, list):
        raw_entities = []

    # -------------------------
    # Entités
    # -------------------------

    for raw in raw_entities:

        if not isinstance(raw, dict):
            continue

        name = str(raw.get("name", "")).strip()

        if not name:
            continue

        entity_type = normalize_entity_type(raw.get("type"))
        properties = clean_properties(raw.get("properties"))

        key = (
            entity_type,
            normalize_text(name),
        )

        if not key[1]:
            continue

        if key in entity_by_key:

            entity = entity_by_key[key]

            # Fusion des propriétés.
            for prop_key, prop_value in properties.items():
                if prop_key not in entity.properties:
                    entity.properties[prop_key] = prop_value

            if chunk_id not in entity.source_chunk_ids:
                entity.source_chunk_ids.append(chunk_id)

        else:

            entity_by_key[key] = GraphEntity(
                id=deterministic_entity_id(entity_type, name),
                type=entity_type,
                name=name,
                properties=properties,
                source_chunk_ids=[chunk_id],
            )

    # Index pratique par type + nom normalisé.
    entity_lookup = {
        (
            entity.type,
            normalize_text(entity.name),
        ): entity
        for entity in entity_by_key.values()
    }

    # -------------------------
    # Relations
    # -------------------------

    relationships: list[GraphRelationship] = []

    relationship_keys: set[
        tuple[str, str, str]
    ] = set()

    raw_relationships = extracted.get("relationships", [])

    if not isinstance(raw_relationships, list):
        raw_relationships = []

    for raw in raw_relationships:

        if not isinstance(raw, dict):
            continue

        source_name = str(
            raw.get("source_name", "")
        ).strip()

        target_name = str(
            raw.get("target_name", "")
        ).strip()

        source_type = normalize_entity_type(
            raw.get("source_type")
        )

        target_type = normalize_entity_type(
            raw.get("target_type")
        )

        if not source_name or not target_name:
            continue

        source = entity_lookup.get(
            (
                source_type,
                normalize_text(source_name),
            )
        )

        target = entity_lookup.get(
            (
                target_type,
                normalize_text(target_name),
            )
        )

        # Aucun lien vers une entité non extraite.
        if source is None or target is None:
            continue

        if source.id == target.id:
            continue

        relation_type = normalize_relation(
            raw.get("type")
        )

        properties = clean_properties(
            raw.get("properties")
        )

        key = (
            source.id,
            target.id,
            relation_type,
        )

        if key in relationship_keys:
            continue

        relationship_keys.add(key)

        relationships.append(
            GraphRelationship(
                source_id=source.id,
                target_id=target.id,
                type=relation_type,
                properties=properties,
                source_chunk_ids=[chunk_id],
            )
        )

    return (
        list(entity_by_key.values()),
        relationships,
    )


# ---------------------------------------------------------------------------
# Neo4j reset
# ---------------------------------------------------------------------------

def reset_graph(graph_store: Neo4jGraphStore) -> None:
    """
    Supprime uniquement les données du Knowledge Graph.

    Cela ne touche ni PostgreSQL, ni Chroma, ni les documents.
    """
    cypher = """
    MATCH (n)
    DETACH DELETE n
    """

    with graph_store._driver.session() as session:
        session.run(cypher)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Construit le Knowledge Graph TEKIS à partir "
            "de tous les chunks."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de chunks à traiter.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extraction uniquement, sans écriture Neo4j.",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Supprime le graphe Neo4j avant la construction. "
            "À utiliser uniquement avec intention."
        ),
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit doit être supérieur à 0.")

    app = create_app("development")

    with app.app_context():

        # ---------------------------------------------------------------
        # Chunks
        # ---------------------------------------------------------------

        query = Chunk.query.order_by(Chunk.id)

        if args.limit is not None:
            query = query.limit(args.limit)

        chunks = query.all()

        print(
            f"chunks_selected={len(chunks)}",
            flush=True,
        )

        print(
            f"dry_run={args.dry_run}",
            flush=True,
        )

        # ---------------------------------------------------------------
        # LLM
        # ---------------------------------------------------------------

        llm = OllamaLLMClient(
            app.config["OLLAMA_BASE_URL"],
            app.config["OLLAMA_LLM_MODEL"],
            temperature=0.0,
            top_p=0.9,
            top_k=40,
        )

        # ---------------------------------------------------------------
        # Neo4j
        # ---------------------------------------------------------------

        graph_store = None
        graph = None

        if not args.dry_run:

            graph_store = Neo4jGraphStore(
                app.config["NEO4J_URI"],
                app.config["NEO4J_USER"],
                app.config["NEO4J_PASSWORD"],
            )

            graph = GraphService(graph_store)

            if args.reset:
                print(
                    "[WARNING] Réinitialisation du Knowledge Graph Neo4j...",
                    flush=True,
                )

                reset_graph(graph_store)

                print(
                    "[OK] Graphe Neo4j vidé.",
                    flush=True,
                )

        elif args.reset:

            print(
                "[WARNING] --reset ignoré avec --dry-run.",
                flush=True,
            )

        # ---------------------------------------------------------------
        # Compteurs
        # ---------------------------------------------------------------

        total_entities = 0
        total_relationships = 0

        successful_chunks = 0
        failed_chunks = 0

        # ---------------------------------------------------------------
        # Traitement
        # ---------------------------------------------------------------

        for index, chunk in enumerate(
            chunks,
            start=1,
        ):

            print(
                f"[{index}/{len(chunks)}] chunk={chunk.id}",
                flush=True,
            )

            extracted = extract_graph(
                llm,
                chunk.id,
                chunk.content,
            )

            if not extracted:

                failed_chunks += 1

                print(
                    f"  -> extraction_failed",
                    flush=True,
                )

                continue

            entities, relationships = process_extraction(
                extracted,
                chunk.id,
            )

            successful_chunks += 1

            total_entities += len(entities)
            total_relationships += len(relationships)

            print(
                f"  -> entities={len(entities)} "
                f"relationships={len(relationships)}",
                flush=True,
            )

            # -----------------------------------------------------------
            # Dry run
            # -----------------------------------------------------------

            if args.dry_run:

                for entity in entities:

                    print(
                        "     ENTITY "
                        f"{entity.id} | "
                        f"{entity.type} | "
                        f"{entity.name}",
                        flush=True,
                    )

                for relationship in relationships:

                    print(
                        "     REL "
                        f"{relationship.source_id} "
                        f"--{relationship.type}--> "
                        f"{relationship.target_id}",
                        flush=True,
                    )

                continue

            # -----------------------------------------------------------
            # Écriture Neo4j
            # -----------------------------------------------------------

            assert graph is not None

            # Les entités sont fusionnées avec les éventuelles
            # occurrences précédentes.
            for entity in entities:

                existing = graph.get_entity(
                    entity.id
                )

                if existing is not None:

                    merged_properties = dict(
                        existing.properties
                    )

                    for key, value in entity.properties.items():

                        if key not in merged_properties:
                            merged_properties[key] = value

                    merged_chunks = sorted(
                        set(
                            existing.source_chunk_ids
                            + entity.source_chunk_ids
                        )
                    )

                    entity = GraphEntity(
                        id=existing.id,
                        type=existing.type,
                        name=existing.name,
                        properties=merged_properties,
                        source_chunk_ids=merged_chunks,
                    )

                graph.upsert_entity(entity)

            # -----------------------------------------------------------
            # Relations
            # -----------------------------------------------------------

            for relationship in relationships:

                try:
                    graph.upsert_relationship(
                        relationship
                    )

                except Exception as exc:

                    print(
                        f"  [WARNING] relation_failed "
                        f"{relationship.source_id} "
                        f"--{relationship.type}--> "
                        f"{relationship.target_id}: "
                        f"{exc}",
                        file=sys.stderr,
                        flush=True,
                    )

        # ---------------------------------------------------------------
        # Résumé
        # ---------------------------------------------------------------

        print(
            "",
            flush=True,
        )

        print(
            "=== RÉSUMÉ KNOWLEDGE GRAPH ===",
            flush=True,
        )

        print(
            f"chunks_selected={len(chunks)}",
            flush=True,
        )

        print(
            f"chunks_successful={successful_chunks}",
            flush=True,
        )

        print(
            f"chunks_failed={failed_chunks}",
            flush=True,
        )

        print(
            f"entities_processed={total_entities}",
            flush=True,
        )

        print(
            f"relationships_processed={total_relationships}",
            flush=True,
        )


if __name__ == "__main__":
    main()
