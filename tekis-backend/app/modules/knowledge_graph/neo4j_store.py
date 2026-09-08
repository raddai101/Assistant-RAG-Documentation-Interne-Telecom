"""
Implémentation Neo4j du `GraphStoreContract` (memoire.md §17 décision #13).

**Non testé en conditions réelles dans cet environnement de développement** : aucun
serveur Neo4j n'a pu être installé ici (ni le dépôt Debian officiel de Neo4j, ni
Docker Hub ne sont accessibles depuis les domaines réseau autorisés de ce sandbox —
contrairement à PostgreSQL en Phase 3, installable via `apt` sur les dépôts Ubuntu
officiels). Même limite que Ollama (Phase 2) et le reranker (Phase 3), tracée par
avance en memoire.md §26 plutôt que découverte en fin de phase. Voir
`tests/unit/test_neo4j_store.py` (driver Neo4j entièrement mocké, vérifie la
construction des requêtes Cypher) pour la couverture disponible sans serveur réel.

Le driver Neo4j peut être injecté directement (`driver=...`) pour les tests ; sinon
il est construit à partir de `uri`/`user`/`password`.
"""
import json
import re

from app.modules.knowledge_graph.contracts import GraphEntity, GraphRelationship

_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_type_token(value: str, field_name: str) -> str:
    """
    Neo4j/Cypher ne permet pas de paramétrer les labels/types de relation comme des
    valeurs de requête classiques (limitation connue du langage Cypher) — ils doivent
    être interpolés dans le texte de la requête. Pour éviter toute injection Cypher,
    on n'accepte que des tokens alphanumériques/underscore, jamais la valeur brute
    d'un utilisateur sans validation.
    """
    if not _SAFE_TOKEN_RE.match(value):
        raise ValueError(
            f"{field_name} invalide : '{value}' (seuls lettres, chiffres et "
            f"underscore sont autorisés, pour éviter une injection Cypher)."
        )
    return value


class Neo4jGraphStore:
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        driver=None,
    ):
        if driver is not None:
            self._driver = driver
        else:
            from neo4j import GraphDatabase

            self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def upsert_entity(self, entity: GraphEntity) -> None:
        cypher = (
            "MERGE (e:Entity {id: $id}) "
            "SET e.type = $type, e.name = $name, e.properties = $properties, "
            "e.source_chunk_ids = $source_chunk_ids"
        )
        with self._driver.session() as session:
            session.run(
                cypher,
                id=entity.id,
                type=entity.type,
                name=entity.name,
                properties=json.dumps(entity.properties or {}, ensure_ascii=False),
                source_chunk_ids=entity.source_chunk_ids,
            )

    def upsert_relationship(self, relationship: GraphRelationship) -> None:
        rel_type = _validate_type_token(relationship.type, "relationship.type")
        cypher = (
            "MATCH (a:Entity {id: $source_id}), (b:Entity {id: $target_id}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r.properties = $properties, r.source_chunk_ids = $source_chunk_ids"
        )
        with self._driver.session() as session:
            session.run(
                cypher,
                source_id=relationship.source_id,
                target_id=relationship.target_id,
                properties=json.dumps(relationship.properties or {}, ensure_ascii=False),
                source_chunk_ids=relationship.source_chunk_ids,
            )

    def get_entity(self, entity_id: str) -> GraphEntity | None:
        cypher = "MATCH (e:Entity {id: $id}) RETURN e"
        with self._driver.session() as session:
            record = session.run(cypher, id=entity_id).single()
            if record is None:
                return None
            return self._node_to_entity(record["e"])

    def get_related_entities(
        self, entity_id: str, relationship_type: str | None = None, depth: int = 1
    ) -> list[GraphEntity]:
        depth = max(1, min(int(depth), 5))  # borne raisonnable, évite une requête incontrôlée
        rel_pattern = ""
        if relationship_type is not None:
            rel_type = _validate_type_token(relationship_type, "relationship_type")
            rel_pattern = f":{rel_type}"

        cypher = (
            f"MATCH (e:Entity {{id: $id}})-[{rel_pattern}*1..{depth}]-(related:Entity) "
            "RETURN DISTINCT related"
        )
        with self._driver.session() as session:
            records = session.run(cypher, id=entity_id)
            return [self._node_to_entity(record["related"]) for record in records]

    def delete_entity(self, entity_id: str) -> None:
        cypher = "MATCH (e:Entity {id: $id}) DETACH DELETE e"
        with self._driver.session() as session:
            session.run(cypher, id=entity_id)

    def find_entities_by_source_chunk_ids(self, chunk_ids: list[int]) -> list[GraphEntity]:
        if not chunk_ids:
            return []
        cypher = (
            "MATCH (e:Entity) "
            "WHERE any(cid IN e.source_chunk_ids WHERE cid IN $chunk_ids) "
            "RETURN DISTINCT e"
        )
        with self._driver.session() as session:
            records = session.run(cypher, chunk_ids=chunk_ids)
            return [self._node_to_entity(record["e"]) for record in records]

    def get_related_facts(self, entity_id: str, depth: int = 5) -> list[str]:
        depth = max(1, min(int(depth), 5))
        cypher = (
            f"MATCH (a:Entity {{id: $id}})-[r*1..{depth}]-(b:Entity) "
            "UNWIND r AS rel "
            "WITH startNode(rel) AS source, rel, endNode(rel) AS target "
            "RETURN DISTINCT source.name AS source_name, type(rel) AS relation, "
            "target.name AS target_name, rel.properties AS properties"
        )
        with self._driver.session() as session:
            return [
                f"{record['source_name']} --{record['relation']}--> {record['target_name']} "
                f"{record['properties'] or {}}"
                for record in session.run(cypher, id=entity_id)
            ]

    def find_entities_by_query(self, query: str) -> list[GraphEntity]:
        terms = [term.lower() for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{3,}", query)]
        if not terms:
            return []
        cypher = (
            "MATCH (e:Entity) WHERE any(term IN $terms WHERE "
            "toLower(e.name) CONTAINS term OR toLower(e.id) CONTAINS term) RETURN DISTINCT e"
        )
        with self._driver.session() as session:
            return [self._node_to_entity(record["e"]) for record in session.run(cypher, terms=terms)]

    @staticmethod
    def _node_to_entity(node) -> GraphEntity:
        properties = node.get("properties", {}) or {}
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                properties = {"raw": properties}
        return GraphEntity(
            id=node["id"],
            type=node["type"],
            name=node["name"],
            properties=properties,
            source_chunk_ids=node.get("source_chunk_ids", []) or [],
        )
