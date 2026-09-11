# TEKIS — Dataset d'évaluation reconstruit

Source de vérité : `tekis_db.sql`, extrait du dump PostgreSQL `tekis_db.dump`.

## Corpus

- Documents : 65
- Versions documentaires : 65
- Chunks : 337

## Questions

Total : 180

Répartition :
- factual : 120
- multi_chunk : 20
- kg : 10
- memory_context : 10
- abstention : 10
- citation_version : 10

## Principe

Les questions factuelles et multi-chunks sont ancrées dans les contenus réels de la table `chunks`.
Les questions KG utilisent plusieurs sources documentaires.
Les questions de mémoire utilisent explicitement un `conversation_history`.
Les questions d'abstention sont volontairement hors corpus.
Les questions citation/version vérifient les métadonnées de provenance.

## Statut

`gold_candidate` : dataset reconstruit et contrôlé structurellement, mais une relecture humaine finale reste recommandée avant publication académique.

Le benchmark A→G ne doit être lancé qu'après cette validation finale.
