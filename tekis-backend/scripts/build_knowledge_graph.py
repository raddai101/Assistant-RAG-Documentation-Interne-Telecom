"""
Construit le Knowledge Graph TEKIS à partir des chunks documentaires.

Principes :
- traite les chunks du corpus, sans logique métier spécifique à Sentinelle ;
- utilise OllamaLLMClient / Qwen3 pour extraire les faits explicites ;
- n'invente aucune entité ni relation ;
- conserve la provenance par chunk ;
- utilise des identifiants déterministes ;
- tolère les erreurs / timeouts Ollama avec retries ;
- permet un test limité avec --limit ;
- permet un --dry-run sans écriture Neo4j ;
- permet --reset pour vider le graphe avant reconstruction.

Le graphe est stocké sous forme :
    (:Entity {
        id,
        type,
        name,
        properties,
        source_chunk_ids
    })

Les relations portent un type en UPPER_SNAKE_CASE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from typing import Any

from app import create_app
from app.models.chunk import Chunk
from app.modules.generation.ollama_client import OllamaError, OllamaLLMClient
from app.modules.knowledge_graph.contracts import (
    GraphEntity,
    GraphRelationship,
)
from app.modules.knowledge_graph.neo4j_store import Neo4jGraphStore
from app.modules.knowledge_graph.service import GraphService


# ---------------------------------------------------------------------------
# Ontologie TEKIS
# ---------------------------------------------------------------------------

ENTITY_TYPES = {
    "PROJECT",
    "SUPPLIER",
    "COMPANY",
    "CONTRACT",
    "SITE",
    "INCIDENT",
    "DOCUMENT",
    "DEPARTMENT",
    "PERSON",
    "PRODUCT",
    "SERVICE",
    "TECHNOLOGY",
    "EQUIPMENT",
    "NETWORK",
    "CUSTOMER",
    "LOCATION",
    "EVENT",
}

DEFAULT_ENTITY_TYPE = "DOCUMENT"

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_:-]+$")
SAFE_RELATION_RE = re.compile(r"^[A-Za-z0-9_]+$")


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def parse_json_object(text: str) -> dict[str, Any]:
    """
    Extrait le premier objet JSON exploitable de la réponse LLM.

    Qwen peut parfois entourer le JSON de texte ou de ```json ... ```.
    On nettoie donc les fences puis on cherche un objet JSON.
    """
    if not text:
        return {}

    cleaned = text.strip()

    # Suppression des fences Markdown éventuelles.
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # Cas idéal : réponse entièrement JSON.
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    # Fallback : rechercher le premier objet JSON.
    start = cleaned.find("{")
    if start == -1:
        return {}

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(cleaned)):
        char = cleaned[index]

        if escaped:
            escaped = False
            continue

        if char == "\\" and in_string:
            escaped = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

            if depth == 0:
                candidate = cleaned[start:index + 1]
                try:
                    parsed = json.loads(candidate)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    return {}

    return {}


def normalize_entity_type(value: Any) -> str:
    """
    Normalise le type d'une entité vers l'ontologie autorisée.
    """
    normalized = str(value or DEFAULT_ENTITY_TYPE)
    normalized = normalized.strip().upper()
    normalized = re.sub(r"\s+", "_", normalized)

    if normalized in ENTITY_TYPES:
        return normalized

    return DEFAULT_ENTITY_TYPE


def normalize_relation_type(value: Any) -> str:
    """
    Normalise et sécurise le type d'une relation.
    """
    normalized = str(value or "RELATED_TO").strip().upper()
    normalized = re.sub(r"[^A-Z0-9_]", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    normalized = normalized.strip("_")

    if not normalized:
        return "RELATED_TO"

    return normalized


def normalize_name(value: Any) -> str:
    """
    Nettoie le nom d'une entité sans modifier son sens.
    """
    return str(value or "").strip()


def deterministic_entity_id(entity_type: str, name: str) -> str:
    """
    Génère un identifiant déterministe et stable.

    Exemple :
        department_direction_marketing
        project_projet_sentinnelle_5g

    Le hash court évite les collisions entre noms très proches.
    """
    normalized_type = normalize_entity_type(entity_type).lower()

    normalized_name = name.strip().lower()
    normalized_name = re.sub(r"\s+", "_", normalized_name)
    normalized_name = re.sub(r"[^a-z0-9À-ÿ_-]", "_", normalized_name)
    normalized_name = re.sub(r"_+", "_", normalized_name)
    normalized_name = normalized_name.strip("_")

    # Conversion volontaire des caractères accentués les plus courants.
    replacements = str.maketrans(
        {
            "à": "a",
            "â": "a",
            "ä": "a",
            "á": "a",
            "ã": "a",
            "å": "a",
            "ç": "c",
            "é": "e",
            "è": "e",
            "ê": "e",
            "ë": "e",
            "î": "i",
            "ï": "i",
            "ì": "i",
            "í": "i",
            "ô": "o",
            "ö": "o",
            "ò": "o",
            "ó": "o",
            "ù": "u",
            "û": "u",
            "ü": "u",
            "ú": "u",
            "ÿ": "y",
            "ñ": "n",
        }
    )

    normalized_name = normalized_name.translate(replacements)

    if not normalized_name:
        normalized_name = "unknown"

    # Limite la taille de l'ID.
    normalized_name = normalized_name[:100].strip("_")

    # Hash pour garantir une stabilité même en cas de normalisation identique.
    digest = hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:8]

    return f"{normalized_type}_{normalized_name}_{digest}"


def normalize_properties(value: Any) -> dict[str, Any]:
    """
    Ne conserve que des propriétés JSON sérialisables.
    """
    if not isinstance(value, dict):
        return {}

    result: dict[str, Any] = {}

    for key, item in value.items():
        key_str = str(key).strip()

        if not key_str:
            continue

        # Évite des structures trop complexes générées accidentellement.
        if isinstance(item, (str, int, float, bool)) or item is None:
            result[key_str] = item

    return result


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def build_extraction_prompt(chunk_id: int, content: str) -> str:
    """
    Prompt volontairement court et contraint.

    Objectif :
    - réduire le temps de génération ;
    - éviter que Qwen produise une analyse longue ;
    - obtenir directement un JSON exploitable.
    """

    return f"""
Tu extrais des faits pour le Knowledge Graph d'une entreprise télécom.

Règles STRICTES :
1. Utilise uniquement les faits explicitement présents dans le texte.
2. N'invente rien.
3. N'infère rien qui n'est pas écrit.
4. Crée uniquement les entités réellement mentionnées.
5. Crée une relation uniquement si le texte établit explicitement cette relation.
6. Les entités doivent avoir un nom lisible.
7. Le type doit être l'un de :
   PROJECT, SUPPLIER, COMPANY, CONTRACT, SITE, INCIDENT,
   DOCUMENT, DEPARTMENT, PERSON, PRODUCT, SERVICE,
   TECHNOLOGY, EQUIPMENT, NETWORK, CUSTOMER, LOCATION, EVENT.
8. Chaque relation doit avoir un type UPPER_SNAKE_CASE.
9. Retourne UNIQUEMENT le JSON, sans explication et sans Markdown.
10. Si aucun fait exploitable n'est présent, retourne :
{{"entities":[],"relationships":[]}}

Format exact :
{{
  "entities": [
    {{
      "type": "PROJECT",
      "name": "nom exact",
      "properties": {{}}
    }}
  ],
  "relationships": [
    {{
      "source": "nom exact source",
      "target": "nom exact cible",
      "type": "RELATION_TYPE",
      "properties": {{}}
    }}
  ]
}}

Chunk source : {chunk_id}

TEXTE :
{content}
""".strip()


# ---------------------------------------------------------------------------
# Extraction LLM
# ---------------------------------------------------------------------------

def extract_graph(
    llm: OllamaLLMClient,
    chunk_id: int,
    content: str,
    retries: int = 2,
    retry_delay: int = 3,
) -> dict[str, Any]:
    """
    Extrait les faits d'un chunk avec retries.

    Important :
    OllamaLLMClient lève OllamaError pour les erreurs réseau/timeout.
    """

    prompt = build_extraction_prompt(chunk_id, content)

    last_error: Exception | None = None

    for attempt in range(1, retries + 2):
        try:
            raw = llm.generate(prompt)
            parsed = parse_json_object(raw)

            if not parsed:
                raise ValueError("Réponse LLM sans objet JSON exploitable.")

            if "entities" not in parsed:
                parsed["entities"] = []

            if "relationships" not in parsed:
                parsed["relationships"] = []

            if not isinstance(parsed["entities"], list):
                parsed["entities"] = []

            if not isinstance(parsed["relationships"], list):
                parsed["relationships"] = []

            return parsed

        except (OllamaError, ValueError, TypeError) as exc:
            last_error = exc

            if attempt <= retries:
                print(
                    f"    [RETRY {attempt}/{retries}] "
                    f"chunk={chunk_id} erreur={exc}"
                )
                time.sleep(retry_delay)

    raise RuntimeError(
        f"Extraction échouée après {retries + 1} tentatives : "
        f"{last_error}"
    )


# ---------------------------------------------------------------------------
# Normalisation de l'extraction
# ---------------------------------------------------------------------------

def normalize_extraction(
    extracted: dict[str, Any],
    chunk_id: int,
) -> tuple[list[GraphEntity], list[GraphRelationship]]:
    """
    Convertit la réponse LLM en objets du contrat TEKIS.

    Les relations référencent les IDs déterministes des entités.
    """

    entities_by_key: dict[tuple[str, str], GraphEntity] = {}

    # ------------------------------------------------------------------
    # Entités
    # ------------------------------------------------------------------

    for raw in extracted.get("entities", []):
        if not isinstance(raw, dict):
            continue

        entity_type = normalize_entity_type(raw.get("type"))
        name = normalize_name(raw.get("name"))

        if not name:
            continue

        entity_id = deterministic_entity_id(entity_type, name)

        if not SAFE_ID_RE.match(entity_id):
            continue

        key = (entity_type, name.casefold())

        properties = normalize_properties(raw.get("properties"))

        if key in entities_by_key:
            existing = entities_by_key[key]

            # Fusion prudente des propriétés.
            existing.properties.update(properties)

            if chunk_id not in existing.source_chunk_ids:
                existing.source_chunk_ids.append(chunk_id)

            continue

        entities_by_key[key] = GraphEntity(
            id=entity_id,
            type=entity_type,
            name=name,
            properties=properties,
            source_chunk_ids=[chunk_id],
        )

    entities = list(entities_by_key.values())

    # Index permettant de retrouver les entités par nom.
    by_name: dict[str, GraphEntity] = {}

    for entity in entities:
        by_name[entity.name.casefold()] = entity

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    relationships: list[GraphRelationship] = []
    relationship_keys: set[tuple[str, str, str]] = set()

    for raw in extracted.get("relationships", []):
        if not isinstance(raw, dict):
            continue

        source_name = normalize_name(
            raw.get("source") or raw.get("source_name")
        )
        target_name = normalize_name(
            raw.get("target") or raw.get("target_name")
        )

        if not source_name or not target_name:
            continue

        source = by_name.get(source_name.casefold())
        target = by_name.get(target_name.casefold())

        # Une relation ne peut être créée que si les deux entités
        # ont réellement été extraites du même chunk.
        if source is None or target is None:
            continue

        relation_type = normalize_relation_type(raw.get("type"))

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
                properties=normalize_properties(raw.get("properties")),
                source_chunk_ids=[chunk_id],
            )
        )

    return entities, relationships


# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------

def print_extraction(
    entities: list[GraphEntity],
    relationships: list[GraphRelationship],
) -> None:
    for entity in entities:
        print(
            f"     ENTITY {entity.id} | "
            f"{entity.type} | "
            f"{entity.name}"
        )

    for relationship in relationships:
        print(
            f"     REL {relationship.source_id} "
            f"--{relationship.type}--> "
            f"{relationship.target_id}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construit le Knowledge Graph TEKIS depuis les chunks."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximum de chunks à traiter.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extrait les faits sans écrire dans Neo4j.",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Supprime les entités du graphe avant reconstruction.",
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Nombre de retries après une erreur Ollama.",
    )

    parser.add_argument(
        "--retry-delay",
        type=int,
        default=3,
        help="Délai en secondes entre les retries.",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Température Qwen pour l'extraction.",
    )

    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        parser.error("--limit doit être supérieur à 0.")

    if args.retries < 0:
        parser.error("--retries ne peut pas être négatif.")

    if args.retry_delay < 0:
        parser.error("--retry-delay ne peut pas être négatif.")

    # ------------------------------------------------------------------
    # Application TEKIS
    # ------------------------------------------------------------------

    app = create_app("development")

    with app.app_context():

        llm = OllamaLLMClient(
            app.config["OLLAMA_BASE_URL"],
            app.config["OLLAMA_LLM_MODEL"],
            temperature=args.temperature,
            top_p=0.9,
            top_k=40,
            timeout=300,
        )

        graph = GraphService(
            Neo4jGraphStore(
                app.config["NEO4J_URI"],
                app.config["NEO4J_USER"],
                app.config["NEO4J_PASSWORD"],
            )
        )

        # --------------------------------------------------------------
        # Sélection des chunks
        # --------------------------------------------------------------

        query = Chunk.query.order_by(Chunk.id)

        if args.limit is not None:
            query = query.limit(args.limit)

        chunks = query.all()

        print(f"chunks_selected={len(chunks)}")
        print(f"dry_run={args.dry_run}")
        print(f"retries={args.retries}")
        print(f"llm_model={app.config['OLLAMA_LLM_MODEL']}")
        print()

        # --------------------------------------------------------------
        # Reset optionnel
        # --------------------------------------------------------------

        if args.reset and not args.dry_run:
            print("RESET Neo4j : suppression des entités existantes...")

            existing_entities = graph.find_entities_by_source_chunk_ids(
                [chunk.id for chunk in chunks]
            )

            # Suppression des entités trouvées.
            deleted = set()

            for entity in existing_entities:
                if entity.id in deleted:
                    continue

                graph.delete_entity(entity.id)
                deleted.add(entity.id)

            print(f"entities_deleted={len(deleted)}")
            print()

        # --------------------------------------------------------------
        # Compteurs
        # --------------------------------------------------------------

        chunks_successful = 0
        chunks_failed = 0
        entities_processed = 0
        relationships_processed = 0

        global_entity_ids: set[str] = set()
        global_relationship_keys: set[tuple[str, str, str]] = set()

        # --------------------------------------------------------------
        # Traitement
        # --------------------------------------------------------------

        for index, chunk in enumerate(chunks, start=1):

            print(
                f"[{index}/{len(chunks)}] "
                f"chunk={chunk.id}"
            )

            try:
                extracted = extract_graph(
                    llm,
                    chunk.id,
                    chunk.content,
                    retries=args.retries,
                    retry_delay=args.retry_delay,
                )

                entities, relationships = normalize_extraction(
                    extracted,
                    chunk.id,
                )

                chunks_successful += 1

                # ------------------------------------------------------
                # Déduplication globale
                # ------------------------------------------------------

                unique_entities: list[GraphEntity] = []

                for entity in entities:
                    if entity.id in global_entity_ids:
                        continue

                    global_entity_ids.add(entity.id)
                    unique_entities.append(entity)

                unique_relationships: list[GraphRelationship] = []

                for relationship in relationships:
                    key = (
                        relationship.source_id,
                        relationship.target_id,
                        relationship.type,
                    )

                    if key in global_relationship_keys:
                        continue

                    global_relationship_keys.add(key)
                    unique_relationships.append(relationship)

                # ------------------------------------------------------
                # Écriture Neo4j
                # ------------------------------------------------------

                if not args.dry_run:

                    # Important : les relations ne sont écrites
                    # qu'après les entités.
                    for entity in entities:
                        graph.upsert_entity(entity)

                    for relationship in relationships:
                        graph.upsert_relationship(relationship)

                entities_processed += len(unique_entities)
                relationships_processed += len(unique_relationships)

                print(
                    f"  -> entities={len(entities)} "
                    f"relationships={len(relationships)}"
                )

                if args.dry_run and (entities or relationships):
                    print_extraction(
                        entities,
                        relationships,
                    )

            except Exception as exc:
                chunks_failed += 1

                print(
                    f"  -> extraction_failed"
                )
                print(
                    f"  [ERROR] chunk={chunk.id} "
                    f"{type(exc).__name__}: {exc}"
                )

        # --------------------------------------------------------------
        # Résumé
        # --------------------------------------------------------------

        print()
        print("=== RÉSUMÉ KNOWLEDGE GRAPH ===")
        print(f"chunks_selected={len(chunks)}")
        print(f"chunks_successful={chunks_successful}")
        print(f"chunks_failed={chunks_failed}")
        print(f"entities_processed={entities_processed}")
        print(f"relationships_processed={relationships_processed}")

        if args.dry_run:
            print("neo4j_write=False")
        else:
            print("neo4j_write=True")


if __name__ == "__main__":
    main()