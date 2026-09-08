"""
Implémentation PostgreSQL Full-Text Search du `LexicalSearchContract` (memoire.md
§17 décision #12). Seul fichier du projet qui exécute du SQL brut pour la recherche
lexicale — le reste du système ne connaît que le contrat (§9).

Configuration de recherche : `french` (stemming), car le corpus et les requêtes
métier sont majoritairement en français (préambule memoire.md). Point non garanti à
100% sans corpus télécom réel (tracé en §24, comme la limite Ollama en Phase 2) :
`websearch_to_tsquery` tokenise sur les séparateurs, donc les identifiants exacts
type `SGSN-2024-17` restent en principe trouvables (recherche par tokens), mais le
comportement du stemming français sur du vocabulaire technique/anglais mêlé n'a pas
été validé sur des données réelles — à confirmer par Radda101 en conditions réelles,
comme pour le reranker.
"""
from sqlalchemy import text

from app.extensions import db
from app.modules.retrieval.lexical.contracts import LexicalMatch


class PostgresFtsLexicalSearch:
    def search(
        self, query: str, top_k: int = 20, document_version_ids: list[int] | None = None
    ) -> list[LexicalMatch]:
        # `document_version_ids` (Phase 5) : restreint la recherche lexicale aux
        # versions autorisées (ACL) et temporellement valides — même filtre que côté
        # vectoriel (`ChromaVectorStore.search(where=...)`), appliqué ici en SQL
        # directement, avant que le LLM ne voie quoi que ce soit (§15).
        version_filter_clause = (
            "AND c.document_version_id = ANY(:document_version_ids)"
            if document_version_ids is not None
            else ""
        )
        sql = text(
            f"""
            SELECT c.id AS chunk_id,
                   c.content AS content,
                   c.document_version_id AS document_version_id,
                   c.page AS page,
                   c.section AS section,
                   ts_rank(to_tsvector('french', c.content), websearch_to_tsquery('french', :query)) AS rank
            FROM chunks c
            WHERE to_tsvector('french', c.content) @@ websearch_to_tsquery('french', :query)
            {version_filter_clause}
            ORDER BY rank DESC
            LIMIT :top_k
            """
        )
        params = {"query": query, "top_k": top_k}
        if document_version_ids is not None:
            params["document_version_ids"] = document_version_ids
        rows = db.session.execute(sql, params).mappings().all()

        return [
            LexicalMatch(
                chunk_id=row["chunk_id"],
                content=row["content"],
                rank=float(row["rank"]),
                metadata={
                    "document_version_id": row["document_version_id"],
                    "page": row["page"],
                    "section": row["section"],
                },
            )
            for row in rows
        ]
