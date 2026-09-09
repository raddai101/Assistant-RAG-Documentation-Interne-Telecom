"""
Construction du contexte et du prompt pour la génération sourcée (Phase 2 baseline).

Rappel de scope (memoire.md §13/§14) : ceci est la version *baseline* de la
génération sourcée (objectif §2.2). La validation evidence-first complète (score de
confiance, détection de contradictions) reste Phase 6 — ici, seule l'abstention
« pas de contexte -> pas de réponse inventée » est appliquée, car c'est le minimum
nécessaire pour ne jamais halluciner une source (§17 des instructions).

`extra_context` (Phase 8, memoire.md §2 objectif 9) : bloc de contexte additionnel
optionnel, utilisé par la variante KG-RAG de l'évaluation comparative pour injecter
les entités du Knowledge Graph liées aux extraits retrouvés. Paramètre par défaut
`None` — comportement strictement inchangé pour tout appelant existant (route
`/chat`, Phases 2-6) qui ne le fournit pas (§3.1 « CHANGE IMPLEMENTATION, PRESERVE
CONTRACT »).
"""
from app.modules.retrieval.contracts import VectorSearchResult

PROMPT_TEMPLATE = """Tu es l'assistant documentaire interne d'une entreprise de télécommunications.
Réponds à la question UNIQUEMENT à partir des extraits et des relations de graphe et de la recherche semantique.
Cette question peut nécessiter plusieurs documents : recoupe explicitement les faits,
reconstitue la chaîne Projet en parcourant l'ensemble de mon corpus, et cite uniquement
les noms/titres de documents fournis dans les métadonnées. N'affiche jamais les chunk_id,
identifiants de vecteurs, IDs techniques ou références numériques internes. Ne conclus pas qu'une information est absente
avant d'avoir parcouru tous les extraits et relations entret documents. Si les preuves restent
insuffisantes, dis précisément quelle étape manque — n'invente jamais de contenu.
Les FAITS STRUCTURÉS PRIORITAIRES DU KNOWLEDGE GRAPH font foi pour les valeurs
relationnelles et les SLA.

Extraits :
{context}

Historique de la discussion :
{history}

Question : {query}

Réponse :"""


def build_context(results: list[VectorSearchResult], extra_context: str | None = None) -> str:
    blocks = []
    for i, r in enumerate(results, start=1):
        document_name = (
            r.metadata.get("original_filename")
            or r.metadata.get("document_title")
            or "Document sans nom"
        )
        version = r.metadata.get("version")
        page = r.metadata.get("page")
        location = document_name
        if version is not None:
            location += f" — version {version}"
        if page is not None:
            location += f", page {page}"
        blocks.append(f"[Document {i} | {location}]\n{r.document}")
    context = "\n\n".join(blocks)
    if extra_context:
        context = (
            f"{extra_context}\n\n"
            "INSTRUCTION DE PRIORITÉ : les faits structurés ci-dessus sont extraits "
            "des relations du graphe et priment sur toute formulation narrative ou "
            "valeur contradictoire dans les extraits.\n\n"
            f"{context}"
        )
    return context


def build_prompt(
    query: str,
    results: list[VectorSearchResult],
    extra_context: str | None = None,
    conversation_history: list[dict] | None = None,
) -> str:
    context = build_context(results, extra_context)
    history = "Aucun historique disponible."
    if conversation_history:
        lines = []
        for item in conversation_history[-12:]:
            role = "Utilisateur" if item.get("role") == "user" else "Assistant TEKIS"
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"{role} : {content}")
        if lines:
            history = "\n".join(lines)

    return PROMPT_TEMPLATE.format(
        context=context,
        history=history,
        query=query,
    )
