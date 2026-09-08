# TEKIS — Mémoire du projet

> Ce fichier est la mémoire permanente du projet TEKIS (Telecom Enterprise Knowledge
> Intelligence System). Il doit être lu avant toute modification significative et mis à
> jour après. L'historique n'est jamais supprimé, seulement complété.

**Statut global du projet : Phase 8 — Évaluation (framework implémenté, en attente d'un jeu de données réel et de la résolution des limites héritées avant exploitation scientifique)**
**Dernière mise à jour : Phase 6 acceptée provisoirement avec CONFIDENCE_THRESHOLD=0.5 (décision explicite de Radda101, calibration réelle reportée) ; démarrage Phase 7 (alignement V(n-1)/V(n), analyse d'impact via Knowledge Graph)**
**Dernière mise à jour : Politique ACL Phase 5 confirmée par Radda101 (clôture officielle Phase 5) ; livraison Phase 6 complète (score de confiance, détection de contradictions métadonnée, abstention affinée) — 132/132 tests verts**

---

## 1. Vision

TEKIS n'est pas un chatbot RAG connecté à une base vectorielle. C'est une
infrastructure de **mémoire organisationnelle intelligente** pour une entreprise de
télécommunications (contexte RDC : Orange, Vodacom, Airtel/Africell, etc.), destinée à
transformer un corpus documentaire interne hétérogène (procédures techniques,
administratives, RH, commerciales, décisions de direction, documentation réseau,
contrats, notes de service...) en une base de connaissance interrogeable en langage
naturel, tout en garantissant :

- la **pertinence** de la récupération d'information (hybrid retrieval) ;
- la **sécurité** (accès conditionné aux droits de l'utilisateur, avant génération) ;
- la **temporalité** (quelle version d'un document est valide à quelle date) ;
- la **traçabilité relationnelle** (Knowledge Graph entre entités métier/techniques) ;
- la **fiabilité** de la génération (evidence-first, citations, score de confiance,
  abstention si preuves insuffisantes) ;
- la **détection des changements** entre versions documentaires (Change Intelligence).

Principe directeur : *« Le LLM n'est pas la mémoire de l'entreprise ; il est
l'interface intelligente qui permet d'interroger une mémoire organisationnelle
externe, structurée, sécurisée, temporelle et vérifiable. »*

Question de recherche associée (mémoire académique) : comment concevoir un système de
mémoire organisationnelle intelligente permettant de retrouver, contextualiser,
sécuriser et exploiter la connaissance documentaire d'une entreprise télécom, en
tenant compte des droits d'accès, de l'évolution temporelle des documents et des
relations entre connaissances métier/techniques ?

---

## 2. Objectifs

1. Ingestion contrôlée de documents d'entreprise (PDF, DOCX, XLSX, TXT) avec
   conservation de la structure, des métadonnées, des versions et des permissions.
2. RAG baseline fonctionnel (embeddings + vector search + génération sourcée).
3. Hybrid Retrieval : recherche lexicale (BM25 / codes / acronymes) + recherche
   vectorielle (sémantique) + fusion + reranking.
4. Knowledge Graph représentant l'organisation (départements, projets, équipements,
   sites, procédures, incidents, décisions, versions) et leurs relations.
5. Temporal RAG : versioning documentaire, `valid_from`/`valid_to`, `supersedes`,
   sélection automatique de la version applicable à une date donnée.
6. Access-Controlled RAG : filtrage des documents selon rôle/département/classification
   **avant** construction du contexte envoyé au LLM.
7. Génération evidence-first : citations obligatoires, score de confiance, détection de
   contradictions, abstention si preuves insuffisantes.
8. Change Intelligence : diff entre versions, détection d'impacts (équipes, procédures
   concernées).
9. Évaluation scientifique comparative : LLM seul vs RAG classique vs Hybrid RAG vs
   KG-RAG vs TEKIS complet, sur des métriques de retrieval, grounding, hallucination,
   sécurité, abstention et performance.
10. Exposer toutes ces fonctionnalités via une API REST stable, consommable plus tard
    par un frontend HTML + JavaScript + TailwindCSS (non développé actuellement).

**Hors périmètre actuel (explicitement exclu) :**
- Développement du frontend (HTML/JS/Tailwind) — sera fait à partir d'une maquette
  Figma, dans une phase ultérieure.
- Support multilingue (exclu du périmètre selon le document de synthèse du projet).
- Toute fonctionnalité non demandée ou anticipée hors de la phase en cours.

---

## 3. Architecture actuelle

**Aucune implémentation de code à ce jour.** Le projet est en Phase 0 (analyse et
proposition d'architecture). Rien n'a été codé, aucun service n'existe encore.

### 3.1 Point de décision architecturale nécessitant validation

Deux documents de cadrage donnent deux niveaux d'architecture différents :

- Le prompt maître d'implémentation backend décrit une **application Flask modulaire
  unique** (`backend/app/api/...`, `services/`, `repositories/...`) avec séparation
  stricte API → Service → Repository → Infrastructure.
- L'extension « architecture microservices » décrit une décomposition en **services
  autonomes déployables séparément** (`gateway-service`, `ingestion-service`,
  `knowledge-service`, `retrieval-service`, `governance-service`,
  `generation-service`, `validation-service`, `change-intelligence-service`,
  `evaluation-service`), chacun avec sa propre base de données encapsulée derrière un
  contrat.

**Proposition (à valider) :** démarrer par un **monolithe modulaire Flask** dont les
frontières internes reproduisent exactement les frontières de services cibles
(mêmes noms de modules, mêmes contrats d'interface, mêmes règles d'isolation des
accès aux données — un module ne touche jamais directement la base d'un autre
module, il passe par une interface/contrat Python). Cela respecte le principe
« CHANGE IMPLEMENTATION, PRESERVE CONTRACT » sans payer le coût opérationnel
(déploiement, réseau, orchestration) de vrais microservices dès la Phase 1, alors que
le corpus et la charge ne le justifient pas encore. L'extraction en services
déployables séparément (conteneurs indépendants derrière l'API Gateway) deviendrait
une étape ultérieure explicite si la charge ou l'équipe le justifient.

Raison : les instructions imposent la « modification minimale nécessaire » et une
progression stricte par phases sans complexité inutile ; construire 9 services réseau
séparés dès la Phase 1 contredit ce principe, alors qu'un monolithe modulaire à
contrats stricts satisfait déjà toutes les règles de non-cascade et d'isolation
listées dans l'extension microservices.

→ **VALIDÉ explicitement par Radda101 (propriétaire du projet), Phase 0 session 2.**
Décision actée : architecture **monolithique Flask modulaire** (et non 9
microservices déployés séparément dès le départ). Flask reste le framework backend,
inchangé. Les frontières de modules internes (`app/modules/...`) et les contrats entre
modules décrits ci-dessous restent la référence : elles permettront une extraction en
services séparés plus tard si la charge le justifie, mais ce n'est plus l'option par
défaut de démarrage — c'est désormais une option future explicitement différée (cf.
§20 Fonctionnalités reportées).

### 3.2 Schéma de flux cible (validé conceptuellement par les documents de projet)

```
Utilisateur (futur frontend)
        │
        ▼
   API Gateway (Flask, blueprint "gateway")
        │
        ▼
  Authentification / Identification du rôle
        │
        ▼
  Query Analyzer (intent, entités, reformulation)
        │
        ▼
  ┌─────────────────────────────────────────┐
  │           HYBRID RETRIEVAL               │
  │   Lexical (BM25/FTS) + Vector + Graph    │
  └─────────────────────┬─────────────────────┘
                         ▼
                     Reranker
                         ▼
              Access Control Filter (ACL)
                         ▼
                 Temporal / Version Filter
                         ▼
                   Context Builder
                         ▼
                        LLM
                         ▼
              Validation Layer (evidence,
           confidence, contradiction, abstention)
                         ▼
                   Audit (trace complète)
                         ▼
                      Réponse JSON
```

Point non négociable (rappelé explicitement dans les instructions) : le filtrage ACL
et temporel a lieu **avant** la construction du contexte, jamais après génération.

---

## 4. Stack technique

| Couche | Choix retenu | Statut |
|---|---|---|
| Langage | Python 3.11+ | Proposé |
| Framework web | Flask, **architecture monolithique modulaire** (et non microservices déployés séparément) | **Validé (Radda101, Phase 0 session 2)** |
| Base relationnelle | PostgreSQL (utilisateurs, rôles, permissions, documents, versions, audit) | Proposé — cohabite avec ChromaDB (cf. ligne Vector store) |
| Vector store | **ChromaDB** | **Validé (Radda101, Phase 0 session 2)** — remplace la proposition initiale PostgreSQL+pgvector (§6.2 historique), accès uniquement via `VectorStoreContract` pour ne pas coupler le module `retrieval` à l'implémentation |
| Recherche lexicale | PostgreSQL Full-Text Search (Phase 3), abstrait derrière un contrat (migration possible vers OpenSearch) | **Confirmé (Radda101)** |
| Knowledge Graph | Neo4j (Phase 4), isolé derrière un `GraphService` | **Confirmé disponible en infra (Radda101)** |
| Embeddings | **BGE-M3** | **Validé (Radda101, Phase 0 session 2)** |
| Exécution des modèles (LLM + embeddings) | **Ollama** (exécution locale) | **Validé (Radda101, Phase 0 session 2)** — cohérent avec l'exigence de confidentialité télécom mentionnée dans `recherches_RAG_1.docx` (les documents ne doivent pas quitter l'infrastructure) |
| LLM génération | **Qwen3-4B** (via Ollama), encapsulé derrière un `LLMContract` interchangeable | **Validé (Radda101, Phase 0 session 2)** |
| Reranking | **BAAI/bge-reranker-v2-m3** (cross-encoder) | **Validé (Radda101)** — mode d'exécution (Ollama/HuggingFace Transformers/serveur dédié) à trancher en Phase 3, ce n'est qu'un détail d'implémentation, pas une nouvelle décision de modèle |
| Migrations DB | Alembic | Proposé |
| Tests | pytest | Imposé par les instructions |
| Auth | **JWT + base de données** | **Validé (Radda101, Phase 0 session 2)** |
| Mémoire conversationnelle | Aucune pour l'instant | **Explicitement différée** jusqu'à ce que la solution complète (Phases 1 à 8) soit testée |
| LangChain / LlamaIndex | Non utilisés pour l'instant | **Explicitement différés** — implémentation « from scratch » des contrats internes en attendant |
| Gestion secrets | variables d'environnement + `.env` non versionné + `.env.example` | Imposé par les instructions |

**Résolu (Phase 0, session 2) :** le triplet LLM/Embeddings/Vector store qui était
« non encore défini » est maintenant validé : Qwen3-4B + BGE-M3 + ChromaDB, exécutés
via Ollama. Ce choix répond à la contrainte de confidentialité identifiée dans
`recherches_RAG_1.docx` puisque l'exécution reste locale (Ollama), sans appel à une
API externe.

**Reste non défini :** rien côté modèles pour l'instant — LLM, embeddings, vector
store, reranker et moteur lexical sont tous validés (cf. §17, décisions #7 à #11).
Point d'implémentation restant pour la Phase 3 : le mode d'exécution concret du
reranker (Ollama, HuggingFace Transformers, ou serveur d'inférence dédié), qui n'est
pas une décision de modèle mais un choix d'infrastructure à faire au moment du code.

---

## 5. Structure du projet (proposée, monolithe modulaire à frontières de service)

```
tekis-backend/
│
├── app/
│   ├── __init__.py                # app factory Flask
│   ├── config/                    # configuration par environnement
│   │
│   ├── api/                       # Gateway — routes Flask uniquement (blueprints)
│   │   ├── auth/
│   │   ├── documents/
│   │   ├── search/
│   │   ├── chat/
│   │   ├── ingestion/
│   │   ├── versions/
│   │   ├── audit/
│   │   └── health/
│   │
│   ├── modules/                   # "services" internes = futures frontières microservices
│   │   ├── identity/              # gouvernance identité/rôles
│   │   │   ├── contracts.py
│   │   │   ├── service.py
│   │   │   └── repository.py
│   │   │
│   │   ├── ingestion/             # ingestion-service
│   │   │   ├── contracts.py
│   │   │   ├── parsers/
│   │   │   ├── chunking/
│   │   │   └── service.py
│   │   │
│   │   ├── knowledge/             # knowledge-service (documents, versions, KG)
│   │   │   ├── contracts.py
│   │   │   ├── documents/
│   │   │   ├── temporal/
│   │   │   └── graph/
│   │   │
│   │   ├── retrieval/             # retrieval-service
│   │   │   ├── contracts.py
│   │   │   ├── lexical/
│   │   │   ├── vector/
│   │   │   ├── graph_search/
│   │   │   ├── fusion/
│   │   │   └── reranking/
│   │   │
│   │   ├── governance/            # governance-service (ACL + audit)
│   │   │   ├── contracts.py
│   │   │   ├── acl/
│   │   │   └── audit/
│   │   │
│   │   ├── generation/            # generation-service
│   │   │   ├── contracts.py
│   │   │   ├── llm_client.py
│   │   │   └── context_builder.py
│   │   │
│   │   ├── validation/            # validation-service
│   │   │   ├── contracts.py
│   │   │   ├── evidence.py
│   │   │   ├── confidence.py
│   │   │   ├── contradiction.py
│   │   │   └── abstention.py
│   │   │
│   │   ├── change_intelligence/   # change-intelligence-service
│   │   │   ├── contracts.py
│   │   │   └── diff_engine.py
│   │   │
│   │   └── evaluation/            # evaluation-service
│   │       ├── contracts.py
│   │       └── metrics.py
│   │
│   ├── models/                    # modèles SQLAlchemy (PostgreSQL)
│   ├── schemas/                   # sérialisation/validation (marshmallow ou pydantic)
│   └── extensions.py               # init db, migrate, etc.
│
├── migrations/
├── tests/
│   ├── unit/
│   ├── contract/                  # tests de contrat entre modules
│   └── integration/
├── scripts/
├── data/                          # corpus de test (jamais de données réelles confidentielles)
├── docs/
├── .env.example
├── requirements.txt
├── run.py
├── config.py
└── memoire.md
```

**Statut : proposé, non créé sur disque.**

---

## 6. Base de données (modèle proposé, à valider en Phase 1)

### 6.1 Relationnel (PostgreSQL)

- `users` (id, nom, email, hash mot de passe, département_id, rôle_id, actif)
- `roles` (id, nom, description)
- `departments` (id, nom, parent_id)
- `documents` (id, titre, département_id, classification, owner, created_at, updated_at)
- `document_versions` (id, document_id, version, valid_from, valid_to, status,
  supersedes_version_id, storage_path, checksum)
- `permissions` (id, document_id ou version_id, allowed_roles[], allowed_users[],
  allowed_departments[])
- `chunks` (id, document_version_id, section, page, contenu_brut, position, hash)
- `chunk_embeddings` (chunk_id, vecteur, modèle_embedding, dimension) — table
  `pgvector` séparée pour permettre migration facile
- `audit_log` (id, user_id, timestamp, action, ressources_consultées[], réponse_id,
  autorisé/refusé)
- `sessions` (id, user_id, created_at)
- `feedback` (id, réponse_id, user_id, note, commentaire)
- `graph_entities` / `graph_relations` (si le Knowledge Graph démarre en tables
  relationnelles avant migration Neo4j en Phase 4)

### 6.2 Vector store

**Décision initiale (Phase 0, session 1, proposée) :** `pgvector` sur la table
`chunk_embeddings`, accédé uniquement via un `VectorStoreContract` (`search`,
`upsert`, `delete`, `get`, `health`).

**Décision actuelle (Phase 0, session 2, validée par Radda101) :** le vector store
retenu est **ChromaDB**, et non plus pgvector. La table `chunk_embeddings` définie en
§6.1 est conservée pour la métadonnée relationnelle (quel chunk appartient à quelle
version de document, quel modèle d'embedding a été utilisé) mais les vecteurs
eux-mêmes seront stockés et interrogés dans ChromaDB, jamais dans PostgreSQL. L'accès
reste exclusivement via le `VectorStoreContract` (`search`, `upsert`, `delete`, `get`,
`health`) — c'est ce contrat qui a changé d'implémentation, pas son interface. Le
module `retrieval` ne doit donc nécessiter aucune modification si ChromaDB est
remplacé plus tard par un autre vector store : c'est exactement le principe « CHANGE
IMPLEMENTATION, PRESERVE CONTRACT » mentionné en §3.1.

### 6.3 Knowledge Graph

Phase 4 : entités (Entreprise, Département, Employé, Projet, Équipement, Site,
Procédure, Incident, Contrat, Fournisseur, Technologie, Décision, Version) et relations
(`AFFECTS`, `RELATED_TO`, `OWNS`, `USES`, `LOCATED_AT`, `SUPERSEDES`, `MODIFIES`,
`CAUSED_BY`, `RESPONSIBLE_FOR`, `BELONGS_TO`), accessibles uniquement via un
`GraphServiceContract`.

**Statut : modèle proposé, aucune table créée.**

---

## 7. API (contrat REST proposé, à affiner en Phase 1)

Format de réponse standard :
```json
{ "success": true, "data": {}, "message": null, "error": null }
```

Endpoints envisagés (version `/api/v1/`) :

- `POST /api/v1/auth/login`
- `GET  /api/v1/health`
- `POST /api/v1/documents` (upload + métadonnées)
- `GET  /api/v1/documents`
- `GET  /api/v1/documents/{id}`
- `GET  /api/v1/documents/{id}/versions`
- `POST /api/v1/ingestion` (déclenche pipeline d'ingestion)
- `POST /api/v1/search` (hybrid retrieval brut, sans génération — utile pour debug/éval)
- `POST /api/v1/chat` (pipeline complet RAG → réponse + sources + confiance)
- `GET  /api/v1/versions/{document_id}?date=YYYY-MM-DD` (résolution temporelle)
- `POST /api/v1/compare` (Change Intelligence : diff entre deux versions)
- `GET  /api/v1/audit` (traces, réservé aux rôles autorisés)

**Statut : proposé, à valider et versionner formellement en Phase 1.**

---

## 8. Ingestion

Formats prioritaires : PDF, DOCX, XLSX, TXT. Chaque document ingéré doit conserver :
`document_id`, `version`, `titre`, `département`, `classification`, `valid_from`,
`valid_to`, `supersedes`, `allowed_roles`, `provenance`, `pages`, `sections`.

**Statut : non implémenté (Phase 1).**

---

## 9. Retrieval

Hybrid Retrieval = lexical (BM25/FTS pour codes, acronymes, références type
`SGSN-2024-17`) + vectoriel (sémantique) + fusion + reranking. Justifié par
`recherches_RAG_1.docx`/`_2.docx` : une recherche purement vectorielle échoue sur les
identifiants exacts.

**Statut : baseline implémentée (Phase 2).** Recherche vectorielle simple via
`RetrievalService` (module `retrieval`) : embedding de la requête (BGE-M3 via
Ollama) puis recherche par similarité dans ChromaDB (`VectorStoreContract`). Aucune
fusion lexicale/vectorielle ni reranking à ce stade — c'est l'objet de la Phase 3
(Hybrid Retrieval). Exposé via `POST /api/v1/search` (retrieval brut, sans
génération). Voir §22bis pour le détail de la livraison.

---

## 10. Knowledge Graph

Représente à la fois l'ontologie télécom (BTS, BSC, Core Network, MPLS, etc.) et la
structure organisationnelle/documentaire propre à l'entreprise cliente. Complète les
documents, ne les remplace pas.

**Statut : non implémenté (Phase 4).**

---

## 11. Temporalité

Chaque connaissance porte `valid_from`, `valid_to`, `version`, `status`, `supersedes`,
`superseded_by`. Le backend résout la version applicable à une date donnée **avant**
tout appel au LLM.

**Statut : implémenté (Phase 5, en attente de vérification finale — voir §28).**
`TemporalResolver` (module `governance`) sélectionne, pour chaque document, la
version valide à une date donnée (`as_of`, défaut "maintenant") : si
`valid_from`/`valid_to` sont renseignés, la fenêtre temporelle fait foi ; sinon,
repli explicite sur le statut `ACTIVE` (comportement de fait depuis la Phase 1,
désormais rendu explicite). Résolution **entièrement côté backend**, jamais déléguée
au LLM (§16). Intégré dans `/api/v1/search` et `/api/v1/chat` via un champ optionnel
`as_of` (ISO 8601) dans le corps de la requête.

---

## 12. Sécurité / ACL

Pipeline obligatoire : Identité → Rôle/ACL → Retrieval autorisé → Contexte autorisé →
LLM. Un document interdit ne doit jamais atteindre le contexte du LLM, même s'il est
sémantiquement très pertinent.

**Statut : implémenté (Phase 5, en attente de vérification finale — voir §28).**
Pipeline complet :
1. **Identité** : `POST /api/v1/auth/login` (JWT), décorateur `require_auth` sur
   `/api/v1/search` et `/api/v1/chat` (401 sans token valide).
2. **Rôle/ACL** : `AccessControlService` — politique **default-deny explicite**
   (une version sans aucune `Permission` associée n'est accessible à personne) +
   bypass pour les rôles listés dans `ADMIN_ROLE_NAMES` (config, défaut `admin`).
   **Politique à confirmer par Radda101** (§19, §24).
3. **Retrieval autorisé** : l'intersection ACL × temporel est calculée avant tout
   appel au vector store ou au moteur lexical (`VectorStoreContract.search(where=...)`,
   `LexicalSearchContract.search(document_version_ids=...)`) — jamais de
   post-filtrage après coup.
4. **Contexte autorisé -> LLM** : `GenerationService` ne reçoit que les chunks déjà
   filtrés par `HybridRetrievalService` ; aucune modification de cette classe n'a
   été nécessaire (contrat préservé, §3.1).

---

## 13. Génération

Contexte construit uniquement à partir des preuves autorisées et pertinentes. Le LLM
génère à partir de ce contexte uniquement (pas de connaissance parasite).

**Statut : baseline implémentée (Phase 2).** `GenerationService` (module
`generation`) orchestre retrieval -> construction du contexte -> appel LLM
(Qwen3-4B via Ollama) -> réponse + sources. **Abstention minimale appliquée dès
maintenant** : si le retrieval ne renvoie aucun résultat, le LLM n'est jamais
appelé et aucune réponse n'est inventée (§17 des instructions). La validation
evidence-first complète (score de confiance, détection de contradictions) reste
Phase 6 — non anticipée. Exposé via `POST /api/v1/chat`. Voir §22bis.

---

## 14. Validation

Evidence-first (citations obligatoires), confidence score, détection de contradictions
(version/statut/date/autorité du document), abstention si preuves insuffisantes.

**Statut : implémenté (Phase 6, en attente de vérification finale — voir §30).**
`ValidationService` (module `validation`) orchestre :
- `ConfidenceScorer` : sigmoïde du score du reranker (top résultat) -> confiance
  `[0, 1]`. **Hypothèse non calibrée** (aucun reranker réel disponible dans
  l'environnement de développement, même limite que Phases 2-4).
- `ContradictionDetector` : garde-fou structurel/métadonnée — signale si plusieurs
  versions d'un même document apparaissent simultanément dans les preuves retenues
  (ne devrait jamais arriver vu `TemporalResolver`, Phase 5). **Portée
  volontairement limitée aux métadonnées (version/statut/date), pas d'analyse
  sémantique du contenu** — cf. memoire.md §29 pour le cadrage explicite.
- Abstention si confiance sous `CONFIDENCE_THRESHOLD` (config, défaut `0.5`), **avant
  tout appel au LLM**, en plus de l'abstention Phase 2 (aucun résultat).
`GenerationResult` expose désormais `confidence` et `warnings`, remontés dans
`POST /api/v1/chat`.

---

## 15. Change Intelligence

Alignement V(n-1)/V(n), détection ajouts/suppressions/modifications, analyse d'impact
(équipes, procédures, projets concernés).

**Statut : non implémenté (Phase 7).**

---

## 16. Tests

Stratégie proposée : pytest, trois niveaux — `unit/` (par module), `contract/`
(vérifie que chaque contrat de module reste compatible avec ses consommateurs),
`integration/` (bout en bout sur un corpus de test synthétique, jamais de données
réelles confidentielles). Aucune phase n'est considérée terminée sans tests verts.

**Statut : aucun test écrit à ce jour.**

---

## 17. Décisions techniques

| # | Date/Phase | Décision | Raison | Statut |
|---|---|---|---|---|
| 1 | Phase 0 | Flask obligatoire comme framework backend | Imposé explicitement par les instructions permanentes du projet | Validé (instruction du propriétaire) |
| 2 | Phase 0 | Frontend non développé actuellement | Sera fait plus tard depuis Figma en HTML/JS/Tailwind | Validé (instruction du propriétaire) |
| 3 | Phase 0 (session 1) | Proposition : monolithe modulaire à frontières de service plutôt que microservices déployés séparément dès le départ | Respecte la règle de modification minimale et de progression par phases ; les contrats internes permettent une extraction ultérieure sans réécriture | Proposition initiale — **remplacée par la décision #6** |
| 4 | Phase 0 (session 1) | Vector store et recherche lexicale démarrent sur PostgreSQL (pgvector + FTS) plutôt que sur des services dédiés externes | Réduit la complexité d'infrastructure en Phase 1-3 tout en respectant l'isolation par contrat (migration possible sans réécriture du retrieval) | Proposition initiale — **partiellement remplacée par la décision #7** (le vector store devient ChromaDB ; le FTS PostgreSQL pour la recherche lexicale n'est pas remis en cause à ce stade, à reconfirmer en Phase 3) |
| 5 | Phase 0 (session 1) | LLM, modèle d'embedding, reranker : non choisis | Dépend de contraintes de confidentialité et d'infrastructure non encore communiquées | Partiellement résolu — **voir décision #8** (LLM et embeddings choisis) ; reranker toujours non défini |
| 6 | Phase 0 (session 2) | **Architecture monolithique Flask modulaire confirmée** (et non microservices déployés séparément dès le départ) | Validation explicite du propriétaire du projet (Radda101) ; Flask inchangé comme framework backend | **Validé (Radda101)** |
| 7 | Phase 0 (session 2) | **Vector store = ChromaDB** (remplace la proposition initiale pgvector) | Choix explicite du propriétaire du projet ; s'intègre à la stack Ollama/Qwen3-4B/BGE-M3 sans appel réseau externe (confidentialité) | **Validé (Radda101)** |
| 8 | Phase 0 (session 2) | **LLM de génération = Qwen3-4B, Embeddings = BGE-M3, exécution via Ollama (local)** | Choix explicite du propriétaire du projet ; répond à l'exigence de confidentialité des documents télécom identifiée dans `recherches_RAG_1.docx` (pas de sortie de l'infrastructure) | **Validé (Radda101)** |
| 9 | Phase 0 (session 2) | **Auth = JWT + base de données** | Choix explicite du propriétaire du projet | **Validé (Radda101)** |
| 10 | Phase 0 (session 2) | Mémoire conversationnelle et intégration LangChain/LlamaIndex explicitement différées | Le propriétaire du projet souhaite valider la solution complète (Phases 1 à 8) avant d'ajouter ces couches | **Validé (Radda101) — reporté, voir §20** |
| 11 | Post-clôture Phase 1 | **Reranker = BAAI/bge-reranker-v2-m3** (cross-encoder) | Choix explicite du propriétaire du projet ; répond au dernier point ouvert de la stack retrieval, en cohérence avec l'exécution locale déjà retenue pour LLM/embeddings | **Validé (Radda101)** |
| 12 | Post-clôture Phase 1 | **PostgreSQL Full-Text Search confirmé** comme moteur lexical de l'Hybrid Retrieval (Phase 3) | Confirmation explicite du propriétaire du projet ; clôt le point resté ouvert depuis le pivot de session 2 (§4, §21) | **Validé (Radda101)** |
| 13 | Post-clôture Phase 1 | **Neo4j confirmé disponible en infrastructure** pour le Knowledge Graph (Phase 4) | Confirmation explicite du propriétaire du projet | **Validé (Radda101)** |
| 14 | Phase 5 | **Politique ACL default-deny** : une version de document sans aucune `Permission` associée est inaccessible à tous, y compris un utilisateur authentifié | Posture la plus sûre pour un pipeline « aucun document interdit ne doit atteindre le LLM » (§15) ; implique que tout document ingéré doit recevoir une permission explicite pour devenir interrogeable | **Validé (Radda101)** |
| 15 | Phase 5 | **Bypass ACL pour les rôles listés dans `ADMIN_ROLE_NAMES`** (config, défaut `admin`) | Nécessaire à l'exploitation/l'audit sans devoir lister chaque document individuellement ; nom de rôle configurable, pas codé en dur | **Validé (Radda101)** |
| 16 | Phase 5 | **PyJWT** ajouté comme dépendance (signature/vérification JWT) | Aucun équivalent stdlib pour une signature HMAC + expiration standardisée ; découle directement de la décision #9 (Auth = JWT) déjà validée | **Validé (découle d'une décision déjà actée, pas une nouvelle politique)** |
| 17 | Phase 6 | **Détection de contradictions limitée aux métadonnées** (version/statut/date), pas d'analyse sémantique du contenu | Une analyse sémantique nécessiterait un appel LLM supplémentaire non demandé explicitement ; respecte le périmètre défini en memoire.md §14 (« contradictions version/statut/date/autorité ») | **Cadrage explicite, pas une politique de sécurité — proposé et documenté (§3 des instructions), à ajuster si Radda101 souhaite une détection sémantique plus tard** |
| 18 | Phase 6 | **Seuil de confiance par défaut = 0.5** (`CONFIDENCE_THRESHOLD`), sigmoïde du score reranker | Première estimation raisonnable en l'absence de reranker réel pour calibrer ; configurable par variable d'environnement | **Provisoire — à recalibrer par Radda101 une fois le reranker réel en service (§30)** |

---

## 18. Historique des modifications

- **Phase 0 — Initialisation.** Création de `memoire.md`. Lecture des instructions
  permanentes du projet, du prompt maître d'implémentation backend, de l'extension
  architecture microservices, et des documents `recherches_RAG_1.docx`,
  `recherches_RAG_2.docx`, `TEKIS_Assistant_RAG_Telecom_RDC_Projet.pdf`. Rédaction de
  la proposition d'architecture Phase 0 (ce document, sections 3 à 7 et 17).
  Aucun code écrit. Aucune base de données créée.

- **Phase 0, session 2 — Validation du pivot architecture + stack technique.**
  Radda101 (propriétaire du projet) confirme explicitement : (1) l'architecture
  **monolithique Flask modulaire**, écartant l'option microservices déployés
  séparément dès le départ (Flask reste inchangé) ; (2) la stack technique définitive
  pour cette phase : **LLM = Qwen3-4B, Embeddings = BGE-M3, Vector store = ChromaDB,
  exécution via Ollama, Auth = JWT + base de données** ; (3) le report explicite de la
  mémoire conversationnelle et de l'intégration LangChain/LlamaIndex jusqu'à ce que la
  solution complète soit testée. Mise à jour des sections 3.1, 4, 6.2, 17, 19, 21 en
  conséquence. Les anciennes propositions (pgvector, LLM/embeddings non définis) sont
  conservées dans l'historique (§17, lignes 3-5) et marquées comme remplacées plutôt
  que supprimées. Aucun code écrit à ce stade — cette session ne fait que consolider
  les décisions d'architecture avant le début effectif de la Phase 1.

- **Phase 0, session 3 — Résolution d'une divergence de mémoire + autorisation de
  démarrage du code.** À la reprise du projet, une divergence a été détectée entre le
  présent fichier (stack Ollama/Qwen3-4B/BGE-M3/ChromaDB) et une mémoire de session
  antérieure évoquant une stack différente (Mistral Small 3.2 + PostgreSQL/pgvector)
  ainsi qu'un épisode d'architecture dual-corpus (Global Telecom KB / Enterprise KB)
  suivi d'un revirage vers un corpus unique. Radda101 a tranché explicitement :
  1. **Stack technique confirmée = celle de ce fichier** (Qwen3-4B + BGE-M3 + ChromaDB,
     exécution Ollama, PostgreSQL relationnel, JWT + DB). La mention « Mistral Small
     3.2 / pgvector » d'une mémoire antérieure est invalidée et ne doit plus être
     utilisée.
  2. **Architecture de corpus confirmée = corpus unique (Enterprise KB uniquement)** —
     ce qui est cohérent avec le présent document, qui n'a jamais décrit de séparation
     Global Telecom KB / Enterprise KB (aucune section de ce fichier ne mentionne un
     double corpus ; le point était donc déjà résolu ici, seule une mémoire externe
     désynchronisée en doutait).
  Décision consignée ici conformément à la règle « ne jamais écraser l'historique » :
  l'ancienne mention Mistral/pgvector et l'épisode dual-corpus restent traçables dans
  cette note explicative, marqués comme invalidés, plutôt que supprimés silencieusement.
  **Autorisation explicite reçue de Radda101 pour démarrer l'implémentation du code
  backend** — la Phase 1 (Corpus et ingestion) commence donc à partir de cette session.

- **Phase 1 — Livraison incrémentale n°1 : squelette applicatif + module `ingestion`
  (parsers + chunking).** Fichiers créés (voir §5 pour l'arborescence de référence) :
  - `requirements.txt`, `.env.example`, `config.py`, `run.py`
  - `app/__init__.py` (app factory), `app/extensions.py` (db, migrate)
  - `app/models/identity.py` (`User`, `Role`, `Department`), `app/models/document.py`
    (`Document`, `DocumentVersion`, `Permission`, `DocumentStatus`),
    `app/models/chunk.py` (`Chunk`, `ChunkEmbeddingMeta` — métadonnée uniquement, le
    vecteur réel restera dans ChromaDB conformément à §6.2), `app/models/audit.py`
    (`AuditLog`, `Session`, `Feedback`)
  - `app/api/health/__init__.py` — premier blueprint, route pure sans logique métier
  - `app/modules/ingestion/contracts.py` (`ParsedDocument`, `DocumentParser`,
    `ChunkResult`, `Chunker` — contrat stable du module)
  - `app/modules/ingestion/parsers/` — `PdfParser` (pypdf), `DocxParser`
    (python-docx), `XlsxParser` (openpyxl), `TxtParser`, plus une factory
    `get_parser_for()` par extension
  - `app/modules/ingestion/chunking/chunker.py` — `FixedSizeChunker` (taille fixe +
    chevauchement, respecte les frontières de page/feuille)
  - `app/modules/ingestion/service.py` — `IngestionService.process_file()` (parse +
    chunk, fonction pure) et calcul de checksums (SHA-256 fichier et chunk)

  **Tests :** 9 tests unitaires (`tests/unit/test_health.py`,
  `test_chunker.py`, `test_parsers.py`) — **tous verts**. Vérification manuelle
  supplémentaire : `db.create_all()` crée sans erreur les 11 tables du schéma complet
  (`departments`, `roles`, `users`, `documents`, `document_versions`, `permissions`,
  `chunks`, `chunk_embeddings`, `audit_log`, `sessions`, `feedback`).

  **Volontairement non fait à ce stade (prochaine étape, pas encore commencée) :**
  - aucun repository ni écriture en base pour les documents/chunks (le service
    `IngestionService` est une fonction pure parse→chunk, sans persistance) ;
  - aucune route API `POST /api/v1/ingestion` exposée (seul `GET /api/v1/health`
    existe) ;
  - aucun appel à ChromaDB ni à Ollama (prévu Phase 2 — embeddings + génération) ;
  - aucune logique d'auth JWT ni d'ACL (prévu Phase 5) ;
  - migrations Alembic non initialisées (`flask db init`) — à faire dès qu'une base
    PostgreSQL réelle est disponible, pour l'instant les tests utilisent SQLite en
    mémoire (`TestingConfig`).

- **Phase 1 — Livraison incrémentale n°2 : persistance + routes API.** Fichiers
  ajoutés/modifiés :
  - `app/modules/ingestion/repository.py` (nouveau) — `IngestionRepository`, seul
    point d'accès DB pour `Document`/`DocumentVersion`/`Chunk` (§9). Gère la création
    d'un nouveau document ou d'une nouvelle version d'un document existant
    (`document_id` fourni), le calcul du numéro de version suivant, et le passage au
    statut `SUPERSEDED` de la version remplacée quand `supersedes_version_id` est
    fourni.
  - `app/modules/ingestion/service.py` (modifié) — ajout de `IngestionService.ingest()`
    : pipeline complet parse → chunk → stockage fichier (copie dans
    `INGESTION_STORAGE_DIR` avec nom UUID) → persistance transactionnelle (rollback
    en cas d'erreur). `process_file()` conservé tel quel (fonction pure, inchangée)
    pour les tests unitaires ; nouvelle méthode privée `_parse_and_chunk()` qui
    sélectionne le parser via `original_filename` (et non le chemin du fichier
    temporaire, qui n'a pas d'extension fiable après upload HTTP).
  - `app/api/ingestion/__init__.py` (nouveau) — `POST /api/v1/ingestion` (upload
    multipart `file` + champs `title`, `department_id`, `classification`, `owner_id`,
    `document_id`, `supersedes_version_id`). Route HTTP pure, délègue tout à
    `IngestionService`.
  - `app/api/documents/__init__.py` (nouveau) — `GET /api/v1/documents/<id>` (lecture
    seule, sans filtrage ACL — non implémenté avant Phase 5).
  - `app/__init__.py` (modifié) — enregistrement des deux nouveaux blueprints.
  - `tests/integration/test_ingestion_api.py` (nouveau) — 4 tests : ingestion réussie
    + vérification via GET, titre manquant → 400, extension non supportée → 400,
    upload d'une nouvelle version d'un document existant → ancienne version passée à
    `SUPERSEDED`, nouvelle version active.

  **Bug rencontré et corrigé (§19) :** le parser était initialement sélectionné selon
  l'extension du fichier temporaire créé par `tempfile.mkstemp()` (sans extension),
  causant une erreur 400 systématique sur tout upload valide. Corrigé en sélectionnant
  le parser via `original_filename` (nom du fichier tel qu'envoyé par le client) tout
  en lisant le contenu depuis le chemin temporaire réel.

  **Résultat :** 13 tests (9 unitaires + 4 intégration), tous verts.

  **Toujours volontairement non fait :** aucun appel ChromaDB/Ollama (Phase 2),
  aucune auth JWT/ACL (Phase 5), migrations Alembic non initialisées (nécessite une
  instance PostgreSQL réelle).

- **Phase 1 — Livraison incrémentale n°3 (finale) : validation réelle + quarantaine.**
  Dernière étape de la Phase 1 avant clôture, à la demande explicite de Radda101.
  Fichiers ajoutés/modifiés :
  - `app/modules/ingestion/validation.py` (nouveau) — `FileValidator` : taille réelle
    du fichier (rejet si 0 octet ou > `MAX_UPLOAD_SIZE_MB`), extension dans la liste
    blanche (PDF/DOCX/XLSX/TXT), et surtout **contrôle du type réel du contenu**
    (signature/structure interne) indépendamment de l'extension déclarée :
    - PDF : en-tête `%PDF-` ;
    - DOCX/XLSX : structure ZIP valide + présence du fichier interne attendu
      (`word/document.xml` / `xl/workbook.xml`) — détecte une extension trompeuse
      (ex. exécutable renommé en `.xlsx`) ;
    - TXT : absence d'octets nuls + décodable en UTF-8 ;
    - garde-fou anti zip-bomb sur les formats ZIP (nombre d'entrées et taille
      décompressée totale plafonnés).
    **Choix technique tracé :** détection par signature en pure stdlib (`zipfile`)
    plutôt que `python-magic`/`libmagic`, pour éviter une dépendance système
    supplémentaire non indispensable (§10 des instructions).
  - `app/modules/ingestion/quarantine.py` (nouveau) — `QuarantineManager` : tout
    fichier uploadé est d'abord écrit dans `QUARANTINE_DIR` (jamais directement dans
    `INGESTION_STORAGE_DIR`). `release()` déplace un fichier validé vers le stockage
    définitif ; `reject()` déplace un fichier non conforme vers
    `quarantine/rejected/` avec un fichier `.reason.txt` horodaté documentant le
    motif — jamais de suppression silencieuse (§14).
  - `app/modules/ingestion/service.py` (modifié) — `ingest()` prend désormais en
    entrée un chemin déjà en quarantaine (`quarantine_file_path`, plus
    `source_file_path`) et orchestre : validation → parse/chunk → libération vers le
    stockage définitif → persistance. Toute erreur de validation OU de parsing après
    validation entraîne un rejet tracé en quarantaine.
  - `app/api/ingestion/__init__.py` (modifié) — met le fichier reçu en quarantaine
    dès réception (`QuarantineManager.stage()`), ne fait plus de vérification de
    taille ad hoc (déléguée à `FileValidator` + à `MAX_CONTENT_LENGTH`).
  - `app/__init__.py` (modifié) — `app.config["MAX_CONTENT_LENGTH"]` positionné à
    partir de `MAX_UPLOAD_SIZE_MB` : la limite de taille est désormais appliquée au
    niveau WSGI par Werkzeug (rejet HTTP 413 automatique), en plus du contrôle
    applicatif de `FileValidator` (défense en profondeur).
  - `config.py`, `.env.example` (modifiés) — ajout de `QUARANTINE_DIR`.
  - Tests : `tests/unit/test_validation.py` (9 tests), `tests/unit/test_quarantine.py`
    (4 tests), `tests/integration/test_ingestion_api.py` (5 tests supplémentaires :
    contenu texte déguisé en PDF, DOCX/XLSX valides, fichier vide, upload trop
    volumineux → 413, quarantaine vide après succès).

  **Bug trouvé et corrigé pendant les tests manuels bout-en-bout (§19) :** un PDF
  avec un en-tête `%PDF-` valide mais un contenu tronqué passait la validation de
  signature puis faisait planter le parsing avec une `PdfStreamError` non interceptée
  par la route API → réponse 500 non voulue. Corrigé : toute erreur de parsing
  survenant après une validation de signature réussie est désormais convertie en
  `FileValidationError` (réponse 400 propre), le fichier est rejeté et tracé en
  quarantaine. Test de régression ajouté
  (`test_ingest_pdf_with_valid_signature_but_corrupted_content_returns_400`).

  **Résultat : 32 tests (21 unitaires + 11 intégration), tous verts.**

- **Post-clôture Phase 1 — Résolution des derniers points ouverts de la stack
  retrieval/KG.** Radda101 confirme explicitement les trois derniers points laissés
  en attente en §21 : (1) **reranker = BAAI/bge-reranker-v2-m3** ; (2) **PostgreSQL
  Full-Text Search confirmé** comme moteur lexical pour l'Hybrid Retrieval (Phase 3) ;
  (3) **Neo4j confirmé disponible en infrastructure** pour le Knowledge Graph
  (Phase 4). Mise à jour de §4 et §17 (décisions #11-13) en conséquence. Plus aucun
  point ouvert ne bloque la Phase 3 ou la Phase 4 côté choix de modèles/outils ; seul
  reste un détail d'implémentation (mode d'exécution du reranker) à trancher au
  moment du code de la Phase 3. Aucun code écrit à ce stade — cette entrée ne fait que
  consolider des décisions avant que ces phases ne commencent.

- **Phase 2 — Livraison incrémentale n°1 : modules `retrieval` et `generation`
  (RAG baseline).** Autorisation explicite reçue de Radda101 pour démarrer la
  Phase 2. Fichiers créés :
  - `app/modules/retrieval/contracts.py` (`VectorStoreContract`, `VectorRecord`,
    `VectorSearchResult` — contrat stable, memoire.md §6.2)
  - `app/modules/retrieval/vector/chroma_store.py` (`ChromaVectorStore` — seule
    implémentation du contrat, seul fichier du projet qui importe `chromadb`)
  - `app/modules/retrieval/repository.py` (`RetrievalRepository` — accès DB isolé
    pour les chunks/embeddings, volontairement séparé d'`IngestionRepository` pour ne
    pas toucher au code de la Phase 1 déjà clos et testé)
  - `app/modules/retrieval/indexing_service.py` (`EmbeddingIndexingService` —
    pipeline explicite et idempotent : ne traite que les chunks sans métadonnée
    d'embedding, transactionnel avec rollback en cas d'incohérence
    chunks/vecteurs)
  - `app/modules/retrieval/service.py` (`RetrievalService` — recherche vectorielle
    simple, sans fusion lexicale ni reranking : c'est la baseline Phase 2, l'Hybrid
    Retrieval reste Phase 3)
  - `app/modules/generation/contracts.py` (`EmbeddingClient`, `LLMClient` — contrats
    stables, indépendants d'Ollama)
  - `app/modules/generation/ollama_client.py` (`OllamaEmbeddingClient`,
    `OllamaLLMClient` — implémentés en `urllib` stdlib, pas de nouvelle dépendance
    HTTP ; voir choix technique tracé en §19)
  - `app/modules/generation/context_builder.py` (construction du prompt à partir des
    extraits retrouvés, avec consigne explicite au LLM de ne jamais inventer)
  - `app/modules/generation/service.py` (`GenerationService` — pipeline complet
    retrieval -> contexte -> LLM -> réponse + sources ; **abstention obligatoire si
    aucun résultat de retrieval**, le LLM n'est alors jamais appelé)
  - `app/api/embeddings/__init__.py` (nouveau, `POST /api/v1/embeddings/reindex` —
    endpoint opérationnel ajouté et signalé, absent de la liste initiale §7 :
    nécessaire pour déclencher l'indexation vectorielle des chunks déjà ingérés en
    Phase 1, sans toucher au pipeline d'ingestion lui-même)
  - `app/api/search/__init__.py` (nouveau, `POST /api/v1/search` — retrieval brut)
  - `app/api/chat/__init__.py` (nouveau, `POST /api/v1/chat` — pipeline RAG complet)
  - `app/__init__.py` (modifié — enregistrement des 3 nouveaux blueprints)
  - `config.py` (modifié — ajout de `RETRIEVAL_TOP_K`, les autres variables Ollama/
    ChromaDB existaient déjà depuis la Phase 0)
  - `requirements.txt` (modifié — ajout de `chromadb==1.5.9` ; **aucune** dépendance
    HTTP ajoutée pour Ollama, `urllib` stdlib suffit)

  **Choix techniques tracés :**
  - Le module `retrieval` possède son propre repository plutôt que de réutiliser
    `IngestionRepository`, pour respecter l'isolation des frontières de module (§9,
    §5) même si les deux repositories accèdent à la table `chunks`.
  - L'indexation des embeddings est un pipeline explicite
    (`POST /api/v1/embeddings/reindex`) déclenché séparément de l'ingestion, plutôt
    qu'une modification du pipeline `IngestionService.ingest()` (Phase 1, clos et
    testé) — respecte la règle de modification minimale (§8).
  - `urllib` (stdlib) plutôt que `requests` pour parler à Ollama : deux appels HTTP
    JSON simples ne justifient pas une dépendance supplémentaire (§10), même logique
    que le choix `zipfile` en Phase 1.

  **Bug trouvé et corrigé pendant les tests (§19) :** `ChromaDB` rejette un dict de
  métadonnées vide (`{}`), ce qui se produit légitimement pour un chunk sans page ni
  section (ex. DOCX/TXT découpé en une seule "page logique", cf. `DocxParser`).
  Corrigé dans `ChromaVectorStore.upsert()` en convertissant tout dict vide en
  `None`, valeur explicitement acceptée par ChromaDB.

  **Limite explicite de cette livraison :** aucun serveur Ollama réel n'était
  accessible dans l'environnement d'implémentation. Les clients
  `OllamaEmbeddingClient`/`OllamaLLMClient` sont donc testés par mock HTTP
  (construction de requête + parsing de réponse), et les tests d'intégration API
  (`/api/v1/embeddings/reindex`, `/api/v1/search`, `/api/v1/chat`) utilisent des
  clients factices injectés par monkeypatch. **ChromaDB, en revanche, a été testé en
  conditions réelles** (mode embarqué `PersistentClient`, aucun serveur externe
  requis). La vérification bout-en-bout avec un Ollama réel (BGE-M3 + Qwen3-4B)
  reste à faire par Radda101 sur son infrastructure avant de considérer la Phase 2
  définitivement close.

  **Résultat : 58 tests (32 hérités de la Phase 1, sans régression, + 26 nouveaux :
  5 ChromaDB réel, 5 clients Ollama mockés, 5 service d'indexation, 4 retrieval/
  génération, 7 intégration API), tous verts.**

---

---

## 19. Problèmes et solutions

- **Problème :** conflit potentiel entre le prompt maître (monolithe Flask modulaire)
  et l'extension microservices (services déployés séparément).
  **Solution proposée (non encore validée) :** cf. section 3.1 — monolithe modulaire
  à frontières et contrats stricts, extraction en services séparés différée à une
  décision ultérieure explicite.

- **Problème :** le choix du LLM/embedding/reranker n'est précisé dans aucun document
  fourni. **Statut : entièrement résolu.** LLM (Qwen3-4B) et embeddings (BGE-M3)
  validés en Phase 0 session 2 ; **reranker (BAAI/bge-reranker-v2-m3) validé
  post-clôture Phase 1**, exécutés/servis localement via Ollama (LLM/embeddings) —
  mode d'exécution du reranker à trancher en Phase 3 (détail d'implémentation, pas un
  nouveau choix de modèle).

- **Problème (résolu) :** conflit entre la proposition initiale « PostgreSQL +
  pgvector » (§6.2, session 1) et le choix ChromaDB validé en session 2.
  **Solution :** le `VectorStoreContract` défini dès la session 1 absorbe ce
  changement d'implémentation sans impact sur le module `retrieval` — voir §6.2 pour
  le détail de la migration décidée.

- **Problème (résolu, Phase 2) :** `ChromaDB` rejette un dict de métadonnées vide
  (`{}`), ce qui se produit légitimement pour un chunk sans page ni section (ex.
  DOCX/TXT). **Solution :** `ChromaVectorStore.upsert()` convertit tout dict vide en
  `None` avant l'appel à ChromaDB.

- **Limite non résolue (Phase 2) :** aucun serveur Ollama réel n'était accessible
  dans l'environnement d'implémentation utilisé pour cette livraison. Les clients
  `OllamaEmbeddingClient`/`OllamaLLMClient` n'ont été vérifiés que par mock HTTP
  (construction de requête + parsing de réponse), jamais contre un vrai serveur
  Ollama servant BGE-M3/Qwen3-4B. **À faire par Radda101 :** lancer
  `POST /api/v1/embeddings/reindex` puis `POST /api/v1/chat` sur un corpus réel avec
  Ollama actif, pour confirmer que le format de réponse réel d'Ollama correspond bien
  à ce qu'attendent les clients (`{"embedding": [...]}` et `{"response": "..."}`) —
  ce format a été supposé d'après la documentation Ollama, pas observé en direct.

- **Décision en attente (Phase 5, pas un bug) :** la politique ACL default-deny +
  bypass `ADMIN_ROLE_NAMES` (§17 décisions #14-15) est implémentée et testée mais
  n'a pas encore été explicitement confirmée par Radda101 — voir le détail complet
  en §28. Tant que cette confirmation n'est pas reçue, considérer cette politique
  comme une proposition raisonnable, pas comme un acquis du projet.

---

## 20. Fonctionnalités reportées

- Frontend (HTML/JS/TailwindCSS) — reporté jusqu'à réception de la maquette Figma.
- Support multilingue — explicitement exclu du périmètre par le document de synthèse
  du projet.
- Extraction en microservices déployés séparément (conteneurs indépendants,
  orchestration) — reportée tant que la charge/l'équipe ne le justifient pas ; les
  contrats internes sont conçus pour permettre cette extraction plus tard.

---

## 21. Prochaines étapes

**Validé depuis la session 2 (ne plus redemander) :** architecture monolithe Flask
modulaire ; LLM = Qwen3-4B ; Embeddings = BGE-M3 ; Vector store = ChromaDB ;
exécution via Ollama ; Auth = JWT + DB ; mémoire conversationnelle et LangChain/
LlamaIndex explicitement différés.

**Validé post-clôture Phase 1 (ne plus redemander) :** Reranker = BAAI/bge-reranker-v2-m3 ;
PostgreSQL Full-Text Search confirmé comme moteur lexical (Phase 3) ; Neo4j confirmé
disponible en infrastructure (Phase 4).

**Plus aucun choix de modèle/outil en attente.** Seul reste un détail d'implémentation
à trancher au moment du code de la Phase 3 : le mode d'exécution concret du reranker
(Ollama / HuggingFace Transformers / serveur d'inférence dédié).

**Étapes immédiates :**
1. ~~Obtenir l'autorisation explicite « COMMENCER PHASE 1 »~~ → **Autorisation reçue
   (Phase 0, session 3)**.
2. ~~Ne pas commencer la Phase 2 avant que la Phase 1 soit testée et validée~~ →
   **Phase 1 clôturée (§22), autorisation Phase 2 reçue de Radda101.**
3. **Phase 2 implémentée (livraison n°1, voir §18) mais pas encore officiellement
   close** : la vérification bout-en-bout avec un Ollama réel (BGE-M3 + Qwen3-4B)
   reste à faire par Radda101 (§19, limite non résolue). Tant que cette vérification
   n'est pas confirmée, considérer la Phase 2 comme « implémentée, en observation »,
   pas « validée ».
4. Ne pas commencer la Phase 3 (Hybrid Retrieval) avant la clôture officielle de la
   Phase 2 et la confirmation par Radda101 que le pipeline fonctionne avec un Ollama
   réel.

## 22. Clôture officielle — Phase 1 (Corpus et ingestion)

**Statut : Phase 1 terminée et validée.** Conformément à la règle d'arrêt obligatoire
en fin de phase (§22 des instructions permanentes), bilan complet avant passage en
Phase 2.

### Ce qui a été livré
- Squelette applicatif Flask complet (app factory, config par environnement isolée
  du code, extensions découplées) respectant la séparation
  API → Services → Repositories → Infrastructure.
- Schéma relationnel PostgreSQL complet (11 tables) couvrant identité, documents,
  versions, permissions, chunks, gouvernance — structure posée pour les phases
  futures sans anticiper leur logique (ACL, temporalité fine, auth JWT restent non
  implémentées, conformément à la progression par phases).
- Module `ingestion` complet et testé :
  - parsers PDF/DOCX/XLSX/TXT derrière un contrat stable (`DocumentParser`) ;
  - chunking à taille fixe avec chevauchement, respectant les frontières de
    page/feuille (`FixedSizeChunker`) ;
  - **validation de sécurité** : taille réelle, extension en liste blanche, contrôle
    du type de contenu réel par signature/structure (indépendant de l'extension
    déclarée), garde-fou anti zip-bomb ;
  - **quarantaine obligatoire** : aucun fichier n'atteint le stockage définitif sans
    validation préalable ; les fichiers rejetés sont tracés avec motif, jamais
    supprimés silencieusement ;
  - persistance transactionnelle (`IngestionRepository`) avec gestion du versioning
    documentaire (nouvelle version, ancienne version marquée `SUPERSEDED`).
- API REST : `GET /api/v1/health`, `POST /api/v1/ingestion`,
  `GET /api/v1/documents/<id>`.

### Tests et résultats
**32 tests, tous verts** (21 unitaires : chunker, parsers, validation, quarantaine ;
11 intégration : bout-en-bout via l'API HTTP, incluant les cas d'attaque/corruption).
Vérification manuelle complémentaire effectuée à deux reprises (création des 11
tables, puis scénarios malveillants réels : PDF tronqué et exécutable renommé en
`.xlsx`), confirmant un comportement conforme dans les deux cas.

### Problèmes rencontrés et résolus
Deux bugs trouvés et corrigés en cours de développement (détail en §19) :
1. Sélection du parser basée sur l'extension du fichier temporaire au lieu du nom de
   fichier original (upload → 400 systématique).
2. Erreur de parsing après validation de signature réussie non interceptée
   (PDF tronqué → 500 au lieu de 400).
Les deux ont été identifiés par des tests bout-en-bout manuels en plus de la suite
automatisée, corrigés, couverts par un test de régression, et tracés ici plutôt que
masqués (§14).

### Ce qui n'a volontairement pas été fait (hors périmètre Phase 1)
- Aucun appel à Ollama ni ChromaDB (embeddings, retrieval, génération — Phase 2/3).
- Aucune authentification JWT ni filtrage ACL (Phase 5).
- Aucune résolution temporelle automatique de version (Phase 5) — le champ `status`
  (`ACTIVE`/`SUPERSEDED`) est mis à jour, mais `valid_from`/`valid_to` restent
  inexploités pour l'instant.
- Aucune migration Alembic initialisée (nécessite une instance PostgreSQL réelle ;
  les tests utilisent SQLite en mémoire).
- Aucun Knowledge Graph, aucune Change Intelligence (respectivement Phase 4 et
  dernière étape du projet, comme rappelé explicitement dans les instructions
  permanentes).

### Prochaine étape
En attente d'autorisation explicite de Radda101 pour démarrer la **Phase 2 — RAG
baseline** (intégration Ollama pour les embeddings BGE-M3 et la génération
Qwen3-4B, stockage vectoriel ChromaDB, premier pipeline de retrieval simple sur le
corpus ingéré en Phase 1).

---

## 23. Clôture officielle — Phase 2 (RAG baseline)

**Statut : Phase 2 terminée et validée.** La limite bloquante notée ci-dessus (§23
initial, conservé tel quel plus bas pour l'historique) est levée : **Radda101 a
confirmé avoir testé le pipeline complet sur son infrastructure avec un serveur
Ollama réel (Qwen3-4B + BGE-M3)** et validé que `POST /api/v1/embeddings/reindex`
puis `POST /api/v1/chat` fonctionnent correctement de bout en bout sur son corpus.
Conformément à §22 des instructions permanentes (ne jamais déclarer une phase
terminée sans vérification), cette confirmation explicite du propriétaire du projet
clôt officiellement la Phase 2.

### Bilan original (conservé pour l'historique)

**Statut : implémenté et testé dans les limites du possible ; en attente de
vérification par Radda101 avec un Ollama réel avant clôture officielle (§22 des
instructions permanentes : ne pas déclarer une phase terminée sans vérification).**

### Ce qui a été livré
- Module `retrieval` : contrat `VectorStoreContract`, implémentation ChromaDB
  (`ChromaVectorStore`), repository dédié, service d'indexation idempotent et
  transactionnel (`EmbeddingIndexingService`), service de recherche simple
  (`RetrievalService`).
- Module `generation` : contrats `EmbeddingClient`/`LLMClient`, clients Ollama en
  stdlib (`urllib`), construction de prompt avec consigne anti-hallucination,
  `GenerationService` avec **abstention obligatoire si aucun résultat de retrieval**.
- 3 nouvelles routes : `POST /api/v1/embeddings/reindex`, `POST /api/v1/search`,
  `POST /api/v1/chat`.

### Tests et résultats
**58 tests, tous verts** (32 hérités de la Phase 1 sans régression + 26 nouveaux).
ChromaDB testé en conditions réelles (mode embarqué). Ollama testé uniquement par
mock HTTP (voir limite ci-dessous).

### Ce qui n'a volontairement pas été fait (hors périmètre Phase 2 baseline)
- Aucune fusion lexicale/vectorielle, aucun reranking (Hybrid Retrieval = Phase 3).
- Aucun score de confiance, aucune détection de contradiction (Validation
  evidence-first complète = Phase 6) — seule l'abstention minimale (pas de preuve ->
  pas de réponse) est appliquée.
- Aucun filtrage ACL, aucune résolution temporelle de version dans le retrieval
  (Phase 5) — `RetrievalService` interroge tout le corpus indexé sans restriction.
- Aucun Knowledge Graph, aucune Change Intelligence (Phase 4 et dernière étape du
  projet).

### Limite bloquant la clôture officielle
Aucun serveur Ollama réel n'était accessible dans l'environnement d'implémentation.
Le format de réponse attendu (`{"embedding": [...]}`, `{"response": "..."}`) est
supposé d'après la documentation Ollama, pas observé en direct. **Action requise de
Radda101** avant de considérer la Phase 2 close : exécuter
`POST /api/v1/embeddings/reindex` puis `POST /api/v1/chat` sur son infrastructure
avec Ollama actif (Qwen3-4B + BGE-M3) et confirmer que le pipeline fonctionne de
bout en bout sur un corpus réel.

### Prochaine étape
En attente de la confirmation de Radda101 sur la vérification Ollama réelle. Une
fois confirmée, clôture officielle de la Phase 2 (mise à jour de ce fichier), puis
autorisation à demander explicitement pour la **Phase 3 — Hybrid Retrieval**
(fusion lexicale PostgreSQL FTS + vectoriel, reranking BAAI/bge-reranker-v2-m3 —
choix déjà validés, §17 décisions #11-12).

---

## 24. Démarrage — Phase 3 (Hybrid Retrieval)

**Autorisation explicite reçue de Radda101** (« pour la phase 2 c'est bon continue
avec la phase 3 ») après confirmation de la vérification Ollama réelle — voir §23.

### Portée validée pour cette phase (rappel §9, §17 décisions #11-12)
- **Recherche lexicale** : PostgreSQL Full-Text Search sur `chunks.content`, justifiée
  par `recherches_RAG_1.docx`/`_2.docx` — une recherche purement vectorielle échoue
  sur les identifiants exacts (ex. `SGSN-2024-17`).
- **Fusion** lexical + vectoriel (les deux résultats existent déjà séparément depuis
  la Phase 2 : `RetrievalService` pour le vectoriel).
- **Reranking** : cross-encoder `BAAI/bge-reranker-v2-m3`, exécution locale (cohérent
  avec le choix Ollama/ChromaDB déjà retenu pour la confidentialité).

### Contrainte d'environnement notée avant de commencer
Cet environnement de développement n'a pas d'accès réseau à `huggingface.co`
(domaines réseau autorisés listés en tête de session), nécessaire pour télécharger les
poids du modèle `BAAI/bge-reranker-v2-m3` au premier chargement. **Même limite que
pour Ollama en Phase 2** : le contrat et l'implémentation seront livrés et testés via
un double de test (reranker factice), mais la vérification en conditions réelles avec
le modèle effectivement chargé nécessitera une confirmation de Radda101 sur son
infrastructure avant clôture officielle de cette phase — tracé ici à l'avance plutôt
que découvert en fin de phase.

**Bonne nouvelle en revanche pour le FTS PostgreSQL** : contrairement aux phases
précédentes (tests sur SQLite en mémoire), un vrai serveur **PostgreSQL 16 a été
installé dans cet environnement de développement** pour cette phase, ce qui permet de
tester la recherche lexicale PostgreSQL FTS (fonctions `to_tsvector`/`websearch_to_tsquery`,
non disponibles sur SQLite) en conditions réelles plutôt que par simple mock. Les
migrations Alembic restent non initialisées (point resté ouvert depuis la Phase 1) —
à faire dès qu'une base de production est disponible.

---

## 25. Clôture officielle — Phase 3 (Hybrid Retrieval)

**Statut : Phase 3 terminée et validée.** **Radda101 a confirmé** la vérification
attendue avec le reranker réel sur son infrastructure (« c'est bon pour la phase 3 »).
Conformément à §22 des instructions permanentes, cette confirmation explicite du
propriétaire du projet clôt officiellement la Phase 3.

### Bilan original (conservé pour l'historique)

**Statut : implémenté et testé dans les limites du possible ; en attente de
vérification par Radda101 avec un reranker réel avant clôture officielle (même
logique que la Phase 2, §22 des instructions : ne pas déclarer une phase terminée
sans vérification).**

### Ce qui a été livré
- **Recherche lexicale** : contrat `LexicalSearchContract`, implémentation
  `PostgresFtsLexicalSearch` (PostgreSQL Full-Text Search, config `french`).
  **Testée en conditions réelles** contre un vrai serveur PostgreSQL 16 (installé
  dans cet environnement pour cette phase) — y compris le cas d'usage qui justifie le
  FTS (retrouver un identifiant exact type `SGSN-2024-17`, que le retrieval
  purement vectoriel manque).
- **Fusion** : `reciprocal_rank_fusion()` (RRF, module `fusion.py`), combine les
  classements lexical et vectoriel sans normaliser des scores hétérogènes.
- **Reranking** : contrat `RerankerContract`, implémentation `CrossEncoderReranker`
  (`BAAI/bge-reranker-v2-m3` via `sentence-transformers`, chargement paresseux).
- **`HybridRetrievalService`** : orchestre vectoriel + lexical → fusion → reranking,
  en exposant **exactement la même interface publique** que `RetrievalService`
  (Phase 2) — `GenerationService` n'a subi **aucune modification** (§3.1 « CHANGE
  IMPLEMENTATION, PRESERVE CONTRACT »). Les routes `POST /api/v1/search` et
  `POST /api/v1/chat` utilisent maintenant ce service, sans changement de leur
  contrat HTTP (même requête, même forme de réponse).
- Changement de sémantique tracé (pas silencieux) : le champ `distance` renvoyé par
  `/search` et `/chat` porte désormais le score du reranker (plus haut = plus
  pertinent) et non plus une distance vectorielle brute (plus bas = plus proche en
  Phase 2).
- Correctif d'infrastructure de test : `create_app()` accepte maintenant un
  paramètre `config_overrides` (appliqué avant `db.init_app()`, qui crée le moteur
  SQLAlchemy immédiatement — modifier `app.config` après coup n'avait aucun effet,
  bug découvert et corrigé pendant l'écriture des tests PostgreSQL réels).

### Tests et résultats
**70 tests, tous verts** (58 hérités des Phases 1-2 sans régression + 12 nouveaux :
4 fusion RRF, 3 reranker avec modèle factice injecté, 5 recherche lexicale/hybride
contre un **vrai** PostgreSQL). Les tests hérités de la Phase 2
(`test_phase2_api.py`) ont été adaptés a minima (ajout de doubles de test pour
`PostgresFtsLexicalSearch`/`CrossEncoderReranker`) sans changer leurs assertions
d'origine.

### Ce qui n'a volontairement pas été fait (hors périmètre Phase 3)
- Aucun score de confiance ni détection de contradiction (Validation evidence-first
  complète = Phase 6).
- Aucun filtrage ACL, aucune résolution temporelle de version dans le retrieval
  (Phase 5).
- Aucun Knowledge Graph, aucune Change Intelligence (Phase 4 et dernière étape).
- Pas d'optimisation des poids de fusion (RRF avec k=60, valeur standard non ajustée
  empiriquement — nécessite un corpus réel et des métriques, Phase 8).

### Limite bloquant la clôture officielle
Comme pour Ollama en Phase 2, **aucun accès réseau à `huggingface.co`** dans cet
environnement de développement : le modèle `BAAI/bge-reranker-v2-m3` n'a jamais été
réellement chargé ni exécuté ici. `CrossEncoderReranker` est testé uniquement via un
modèle factice injecté (`tests/unit/test_reranker.py`), qui vérifie la logique
(construction des paires, tri, troncature) mais pas le comportement réel du modèle.
**Action requise de Radda101** avant de considérer la Phase 3 close : exécuter
`POST /api/v1/search` et `POST /api/v1/chat` sur son infrastructure avec le reranker
réellement chargé, et confirmer que le classement final est pertinent sur un corpus
réel (comparer par exemple les résultats avec/sans reranking sur quelques requêtes).

### Note d'infrastructure de développement (pas un bug du code)
Le serveur PostgreSQL installé dans cet environnement de développement ne persiste
pas entre les redémarrages de session (`service postgresql status` peut revenir à
`down`). Sans rapport avec le code applicatif — simple aléa du sandbox de
développement, à redémarrer au besoin (`service postgresql start`) avant de relancer
`tests/integration/test_hybrid_retrieval_real_postgres.py`. Sans incidence sur
l'infrastructure de production de Radda101.

### Prochaine étape
En attente de la confirmation de Radda101 sur la vérification du reranker réel. Une
fois confirmée, clôture officielle de la Phase 3, puis autorisation à demander
explicitement pour la **Phase 4 — Knowledge Graph** (Neo4j, disponibilité déjà
confirmée en infrastructure, §17 décision #13).

---

## 26. Clôture officielle — Phase 4 (Knowledge Graph)

**Statut : Phase 4 terminée et validée.** **Radda101 a confirmé** avoir testé
l'ensemble de la livraison sur son infrastructure (« j'ai déjà tout testé, tu peux
maintenant avancer »), incluant la vérification Neo4j réelle demandée ci-dessous.
Conformément à §22 des instructions permanentes, cette confirmation explicite du
propriétaire du projet clôt officiellement la Phase 4.

### Bilan original (conservé pour l'historique)

**Statut : implémenté et testé dans les limites du possible ; en attente de
vérification par Radda101 avec un Neo4j réel avant clôture officielle (même logique
que les Phases 2 et 3, §22 des instructions : ne pas déclarer une phase terminée
sans vérification).**

### Portée de cette livraison (rappel §3 des instructions : ne pas développer une
fonctionnalité non demandée)
Le module `knowledge_graph` livré ici expose **l'infrastructure du graphe**
(création/lecture/suppression d'entités et de relations, navigation par relation et
profondeur) — pas encore de **peuplement automatique** par extraction d'entités
depuis le texte des chunks, qui nécessiterait un pipeline NLP dédié non demandé
explicitement. Le peuplement reste manuel via l'API pour cette livraison ; son
automatisation est une décision à prendre séparément (à signaler, pas à développer
spontanément — §3).

### Ce qui a été livré
- **Contrats** (`app/modules/knowledge_graph/contracts.py`) : `GraphEntity`,
  `GraphRelationship`, `GraphStoreContract` — traçabilité obligatoire vers les
  sources documentaires via `source_chunk_ids` sur chaque entité/relation, cohérent
  avec la règle des instructions permanentes : le graphe complète les documents, il
  ne devient jamais la source unique de vérité.
- **`Neo4jGraphStore`** (implémentation du contrat) : requêtes Cypher paramétrées
  pour les valeurs, avec validation stricte (regex alphanumérique/underscore) des
  labels/types de relation avant interpolation dans le texte de la requête — Cypher
  ne permet pas de paramétrer les types de relation comme des valeurs classiques,
  d'où ce garde-fou explicite contre l'injection Cypher. Profondeur de navigation
  bornée à 5 (protection contre une requête incontrôlée).
- **`GraphService`** : garde-fou métier — impossible de créer une relation entre deux
  entités dont l'une n'existe pas encore (pas de relation « orpheline » créée
  implicitement).
- **API REST** : `POST /api/v1/graph/entities`, `GET /api/v1/graph/entities/<id>`,
  `DELETE /api/v1/graph/entities/<id>`, `GET /api/v1/graph/entities/<id>/related`
  (paramètres `type`, `depth`), `POST /api/v1/graph/relationships`.

### Tests et résultats
**95 tests, tous verts** (70 hérités des Phases 1-3 sans régression + 25 nouveaux :
9 sur `Neo4jGraphStore` avec un driver Neo4j entièrement factice — vérifient la
construction des requêtes Cypher, le rejet d'un type de relation invalide, et le
plafonnement de la profondeur —, 7 sur `GraphService` avec un store en mémoire,
9 d'intégration API avec `Neo4jGraphStore` monkeypatché).

### Limite bloquant la clôture officielle
**Aucun serveur Neo4j n'a pu être installé ni testé dans cet environnement de
développement** : ni le dépôt Debian officiel de Neo4j, ni Docker Hub ne sont
accessibles depuis les domaines réseau autorisés de ce sandbox (contrairement à
PostgreSQL en Phase 3, installable via les dépôts Ubuntu officiels). Le driver
`neo4j` (bibliothèque cliente Python) est installé et importable, mais aucune
requête Cypher n'a jamais atteint un vrai serveur — seule la construction des
requêtes est vérifiée, pas leur exécution réelle ni les contraintes/index Neo4j
(aucune contrainte d'unicité sur `Entity.id` n'a été créée, par exemple — à faire
côté infrastructure). **Action requise de Radda101** avant de considérer la Phase 4
close : créer quelques entités/relations via l'API sur son infrastructure Neo4j
réelle, vérifier leur présence dans Neo4j Browser/`cypher-shell`, et confirmer que
la navigation (`/related`) renvoie les résultats attendus.

### Prochaine étape
~~En attente de la confirmation de Radda101 sur la vérification Neo4j réelle~~ →
**confirmée.** Phase 4 officiellement close. Démarrage de la **Phase 5 — Temporal +
ACL** ci-dessous (§27).

---

## 27. Démarrage — Phase 5 (Temporal + ACL)

**Autorisation explicite reçue de Radda101** (« j'ai déjà tout testé, tu peux
maintenant avancer », après confirmation Neo4j réelle — voir §26).

### Portée validée pour cette phase (rappel §11, §12, §15 des instructions permanentes)
Pipeline de sécurité obligatoire, non négociable : **Identité → Rôle/ACL → Retrieval
autorisé → Contexte autorisé → LLM**. Aucun document interdit ne doit jamais
atteindre le contexte du LLM, même s'il est sémantiquement très pertinent — le
filtrage n'a jamais lieu après génération.

Éléments déjà présents dans le schéma depuis la Phase 1 (memoire.md §6.1) et
jusqu'ici inexploités, que cette phase vient enfin activer :
- `User.role_id`, `User.department_id`, `Role`, `Department` (module `identity`)
- `Permission.allowed_roles` / `allowed_users` / `allowed_departments` (par document
  ou par version)
- `DocumentVersion.valid_from` / `valid_to` / `status` / `supersedes_version_id`
  (résolution temporelle — la version applicable à une date donnée doit être choisie
  par le backend, **jamais** par le LLM, §16 des instructions)

### Ce qui est prévu dans cette livraison
1. **Authentification JWT** : `POST /api/v1/auth/login` (email/mot de passe →
   access token), décorateur `@require_auth` exposant l'utilisateur courant
   (`g.current_user`) aux routes protégées.
2. **Filtrage ACL** : un nouveau `AccessControlService` détermine, pour un
   utilisateur donné, l'ensemble des `document_version_id` auxquels il a droit
   (rôle, département, ou accès nominatif), à partir de `Permission`. Ce filtre est
   appliqué **avant** l'appel au vector store — au niveau des métadonnées ChromaDB
   (`document_version_id` déjà indexé depuis la Phase 2), pas après coup sur les
   résultats.
3. **Résolution temporelle** : un `TemporalResolver` qui, pour une date donnée
   (par défaut "maintenant"), ne retient que la version `ACTIVE`/valide à cette date
   parmi les versions d'un même document — appliqué au même niveau que l'ACL, avant
   construction du contexte.
4. **Intégration dans `RetrievalService`/`HybridRetrievalService`** (Phase 2/3) :
   ajout d'un paramètre `authorized_document_version_ids` transmis par les routes
   `/api/v1/search` et `/api/v1/chat` une fois l'utilisateur identifié — **aucune
   réécriture** de la logique de fusion/reranking déjà livrée (§3.1 « CHANGE
   IMPLEMENTATION, PRESERVE CONTRACT »).
5. `GET /api/v1/documents/<id>` (Phase 1) reste en lecture libre pour l'instant sauf
   décision contraire — à confirmer avec Radda101 si ce endpoint doit aussi être
   protégé dans cette phase ou seulement le pipeline RAG.

### Point à clarifier avant de coder le filtrage ChromaDB
ChromaDB filtre les métadonnées par égalité/comparaison simple (`$in`, `$eq`), pas
par jointure SQL — filtrer par `document_version_id` autorisé est donc faisable
nativement (`where={"document_version_id": {"$in": [...]}}`), sans changement de
schéma. Ce point est noté ici pour traçabilité, pas parce qu'il bloque le
démarrage.

---

## 28. Clôture officielle — Phase 5 (Temporal + ACL)

**Statut : Phase 5 terminée et validée.** **Radda101 a explicitement confirmé la
politique ACL** (default-deny + bypass `ADMIN_ROLE_NAMES`, §17 décisions #14-15).
Contrairement aux Phases 2/3/4, cette clôture ne dépendait d'aucune vérification
technique sur infrastructure externe (JWT/ACL/temporel sont de la logique
Python/SQL pure, déjà testée avec une vraie base) — seule la confirmation de
politique de sécurité manquait, et elle est reçue.

### Bilan original (conservé pour l'historique)

**Statut : implémenté et testé — mais clôture en attente pour une raison différente
des Phases 2/3/4.** Contrairement à ces phases, rien ici ne dépend d'un service
externe indisponible dans l'environnement de développement (JWT, ACL et résolution
temporelle sont de la logique Python/SQL pure, testée avec une vraie base SQLite).
**Ce qui manque n'est pas une vérification technique mais une confirmation de
politique de sécurité** (§17 décisions #14-15, §24 des instructions : ne jamais
acter silencieusement un choix de sécurité).

### Ce qui a été livré
- Module `identity` : `AuthService` (vérification email/mot de passe,
  `werkzeug.security`), `JWTService` (encodage/décodage, expiration), décorateur
  `require_auth` (relit toujours rôle/département depuis la base, jamais depuis le
  token, pour qu'un changement d'habilitation soit immédiatement effectif).
  Route `POST /api/v1/auth/login`.
- Module `governance` : `AccessControlService` (ACL, politique default-deny +
  bypass `ADMIN_ROLE_NAMES`), `TemporalResolver` (résolution de version par date,
  repli sur statut `ACTIVE`).
- Intégration dans le pipeline existant **sans réécriture** de la logique de
  fusion/reranking (§3.1) : ajout d'un paramètre optionnel
  `authorized_document_version_ids` à `VectorStoreContract.search` (via `where=`),
  `LexicalSearchContract.search` (via `document_version_ids=`), `RetrievalService`,
  `HybridRetrievalService` et `GenerationService`. `None` = pas de restriction
  (rétrocompatible avec tout appel Phase 2/3 existant), ensemble vide = refus total
  sans même interroger le vector store ou PostgreSQL (§15 : jamais de document
  interdit récupéré puis caché après coup).
- `/api/v1/search` et `/api/v1/chat` protégées par `require_auth`, acceptent un
  champ optionnel `as_of` (ISO 8601) pour interroger le corpus tel qu'il était valide
  à une date passée.

### Choix technique tracé
`PyJWT` ajouté comme dépendance (§17 décision #16) — découle mécaniquement de la
décision « Auth = JWT » déjà validée en Phase 0, pas une nouvelle décision de
sécurité en soi.

### Décision de sécurité explicitement en attente de confirmation (§17 #14-15)
1. **Default-deny** : une version de document sans aucune `Permission` associée
   est inaccessible à tous, y compris un utilisateur authentifié non-admin. En
   pratique, **tout le corpus ingéré en Phases 1-4 est actuellement invisible** pour
   `/search` et `/chat` tant qu'aucune `Permission` n'est créée — c'est le
   comportement voulu d'un système « access-controlled » par défaut, mais cela
   mérite une confirmation explicite avant d'être considéré acquis.
2. **Bypass `ADMIN_ROLE_NAMES`** (défaut `{"admin"}`, configurable) : nécessaire à
   l'exploitation, mais le nom de rôle et la portée du bypass (accès à absolument
   tout, y compris temporellement ?) doivent être validés.

**Radda101, merci de confirmer ces deux points** (ou de proposer une politique
différente) pour que la Phase 5 puisse être officiellement close.

### Tests et résultats
**121 tests, tous verts** (95 hérités des Phases 1-4 sans régression + 26 nouveaux :
7 auth/JWT, 7 AccessControlService, 4 TemporalResolver, 1 correctif de fake
existant, 7 intégration Phase 5 dont login réel, filtrage ACL bout en bout par
rôle/département/utilisateur nominatif, et résolution temporelle via `as_of`).

### Ce qui n'a volontairement pas été fait (hors périmètre Phase 5)
- Aucune interface de gestion des `Permission` (créer/lister/révoquer des droits) —
  non demandé, à discuter si besoin opérationnel réel.
- `GET /api/v1/documents/<id>` (Phase 1) reste en lecture libre, non protégée par
  `require_auth` — décision à confirmer par Radda101 (memoire.md §27, point 5).
- Aucun audit détaillé des accès refusés (table `audit_log` existe depuis la
  Phase 1 mais n'est pas encore alimentée) — cohérent avec la portée de la
  Validation evidence-first, Phase 6.

### Prochaine étape
~~En attente de la confirmation de Radda101 sur la politique ACL~~ → **confirmée.**
Phase 5 officiellement close. `GET /api/v1/documents/<id>` reste en lecture libre
pour l'instant (non tranché explicitement — à soulever si besoin opérationnel).
Démarrage de la **Phase 6 — Validation** ci-dessous (§29).

---

## 29. Démarrage — Phase 6 (Validation)

**Autorisation explicite reçue de Radda101** (« continue avec la progression du
projet », après confirmation de la politique ACL — voir §28).

### Portée validée pour cette phase (rappel §14 des instructions permanentes)
« Une réponse TEKIS doit être fondée sur les preuves récupérées. Ne jamais inventer
une source, une citation, une version documentaire, une page. Si les preuves sont
insuffisantes : abstention. » Le vision du projet (§1) précise : score de confiance,
détection de contradictions, abstention si preuves insuffisantes.

**Cadrage important, pour ne pas déborder du périmètre (§3 des instructions) :**
la détection de contradictions visée ici (memoire.md §14 : « contradictions
version/statut/date/autorité du document ») est une détection **structurelle/
métadonnée**, pas une analyse sémantique du contenu des chunks — cette dernière
nécessiterait un appel LLM supplémentaire (coûteux, et non demandé explicitement) et
n'est pas anticipée dans cette livraison. Si Radda101 souhaite une détection
sémantique de contradiction de contenu plus tard, ce sera signalé et proposé
séparément (§3), pas ajouté silencieusement ici.

### Ce qui est prévu dans cette livraison
1. **`ConfidenceScorer`** (module `validation`) : transforme le score du reranker
   (champ `distance` de `VectorSearchResult`, qui porte le score cross-encoder
   depuis la Phase 3 — memoire.md §24) en confiance `[0, 1]` via sigmoïde. **Limite
   explicite à tracer** : le seuil par défaut (`CONFIDENCE_THRESHOLD`) est une
   première estimation non calibrée, faute d'accès à un reranker réel dans cet
   environnement (même limite que Phases 2-4) — à ajuster par Radda101 une fois
   `BAAI/bge-reranker-v2-m3` réellement en service.
2. **`ContradictionDetector`** (module `validation`) : vérifie, parmi les chunks
   retenus après ACL/temporel, si plusieurs versions d'un même document apparaissent
   simultanément (cela ne devrait jamais arriver vu `TemporalResolver`, mais c'est un
   garde-fou défensif plutôt qu'une confiance aveugle dans l'étage précédent).
3. **`ValidationService`** : orchestration confiance + contradictions ->
   `should_abstain` (si confiance sous le seuil) avec motif explicite, sinon
   l'exécution continue normalement.
4. **Intégration dans `GenerationService`** : la validation s'exécute **après**
   retrieval mais **avant** l'appel au LLM (§17 : jamais de réponse générée sans
   preuve suffisante) ; `GenerationResult` gagne deux champs (`confidence`,
   `warnings`), tous deux avec valeurs par défaut pour ne rien casser côté appelants
   existants.
5. Exposition dans `POST /api/v1/chat` : `confidence` et `warnings` ajoutés à la
   réponse JSON.

---

## 30. Bilan de la livraison Phase 6 — Validation (pas encore une clôture officielle)

**Statut : implémenté et testé dans les limites du possible ; en attente de
vérification par Radda101 avec un reranker réel avant clôture officielle (même
limite que les Phases 2/3/4 : problème de calibration technique, pas de décision de
politique en attente comme la Phase 5).**

### Ce qui a été livré
- Module `validation` : `ConfidenceScorer` (sigmoïde du score reranker),
  `ContradictionDetector` (garde-fou métadonnée, versions multiples d'un même
  document), `ValidationService` (orchestration -> décision d'abstention).
- Intégration dans `GenerationService.answer()` : la validation s'exécute entre le
  retrieval et l'appel au LLM ; abstention si confiance insuffisante, **sans jamais
  appeler le LLM** dans ce cas (§17 des instructions).
- `GenerationResult` étendu (`confidence`, `warnings`, valeurs par défaut —
  rétrocompatible) ; `POST /api/v1/chat` expose ces deux champs.
- `config.py` : `CONFIDENCE_THRESHOLD` (défaut `0.5`).

### Cadrage explicite (§17 décision #17)
La détection de contradictions est **structurelle/métadonnée** (version/statut/date),
pas sémantique. Une analyse du contenu des chunks nécessiterait un appel LLM
supplémentaire, non demandé — signalé ici plutôt qu'ajouté silencieusement (§3 des
instructions). À proposer séparément si Radda101 le souhaite.

### Tests et résultats
**132 tests, tous verts** (121 hérités des Phases 1-5 sans régression + 10 nouveaux
sur le module `validation` + 1 test d'intégration `/api/v1/chat` vérifiant
`confidence`/`warnings`). Deux tests hérités (`test_generation_service_returns_
answer_with_sources`, `..._abstains_when_no_retrieval_results`) ont été adaptés pour
injecter un `ValidationService` factice — `GenerationService` dépend désormais de la
DB via `ContradictionDetector`, ce qui aurait cassé leur statut de test unitaire pur
sans cet ajustement (évolution légitime du contrat, pas un contournement de bug,
§14 des instructions).

### Limite bloquant la clôture officielle
Même situation que les Phases 2/3/4 : `BAAI/bge-reranker-v2-m3` n'est pas disponible
dans cet environnement de développement (déjà confirmé fonctionnel par Radda101 en
Phase 3, memoire.md §25). Le seuil `CONFIDENCE_THRESHOLD = 0.5` et la sigmoïde
appliquée au score du reranker sont une hypothèse raisonnable, jamais mesurée sur
des scores réels. **Action requise de Radda101 :** observer la distribution réelle
des scores retournés par le reranker en production, et ajuster
`CONFIDENCE_THRESHOLD` en conséquence (une valeur mal calibrée pourrait soit
abstenir TEKIS trop souvent, soit jamais assez).

### Ce qui n'a volontairement pas été fait (hors périmètre Phase 6)
- Aucune détection sémantique de contradiction de contenu (cadrage explicite
  ci-dessus).
- Aucune notion d'« autorité du document » dans la détection de contradictions
  (mentionnée en memoire.md §14 mais aucune donnée d'autorité/hiérarchie de source
  n'existe encore dans le schéma — à soulever si besoin).
- Aucune UI de citation formatée (les sources restent des identifiants structurés
  `chunk_id`/`document_version_id`/`page`, pas du texte de citation formaté — hors
  périmètre backend actuel, §20 des instructions : frontend non développé).

### Décision de Radda101 — acceptation provisoire du seuil, démarrage Phase 7
**Radda101 a explicitement décidé de ne pas attendre la calibration du reranker réel
pour poursuivre** : « dans un premier temps restons avec un CONFIDENCE_THRESHOLD =
0.5 on va le changer dès que possible, continuons avec la Phase 7 ». Décision tracée
ici plutôt que silencieusement actée (§5 des instructions : conserver l'ancienne
décision, la nouvelle, et la raison du changement) :
- **Ancienne posture** : clôture officielle de la Phase 6 subordonnée à une
  calibration du seuil avec reranker réel (§22 des instructions : ne pas déclarer
  une phase terminée sans vérification).
- **Nouvelle décision** : `CONFIDENCE_THRESHOLD = 0.5` reste la valeur en vigueur
  **provisoirement**, la calibration réelle est reportée à une date ultérieure non
  précisée, et le projet avance sur la Phase 7 sans attendre.
- **Raison** : décision explicite du propriétaire du projet, priorité donnée à
  l'avancement plutôt qu'au blocage sur une calibration fine.
- **Statut Phase 6** : *non close officiellement* au sens strict de la règle §22 —
  c'est une **autorisation explicite de contournement temporaire**, à la demande du
  propriétaire du projet (§25 des instructions : priorité aux exigences explicites
  du propriétaire sur toute autre règle de procédure). Le seuil `CONFIDENCE_THRESHOLD`
  reste marqué *provisoire* dans le code et dans ce document tant que la calibration
  réelle n'a pas eu lieu.

### Prochaine étape
Démarrage immédiat de la **Phase 7 — Change Intelligence** (voir §31).

---

## 31. Bilan de la livraison Phase 7 — Change Intelligence (pas encore une clôture officielle)

**Statut : implémenté et testé. Dépend de la Phase 6 (non close officiellement, §30)
et sollicite optionnellement le Knowledge Graph (Phase 4, jamais vérifié avec un
Neo4j réel — même limite non résolue, memoire.md §26). Clôture officielle de la
Phase 7 donc, par construction, subordonnée à ces deux limites en amont.**

### Portée (rappel memoire.md §15)
« Alignement V(n-1)/V(n), détection ajouts/suppressions/modifications, analyse
d'impact (équipes, procédures, projets concernés). » Implémentée en dernier,
conformément à la règle explicite du projet (« Le Change Intelligent doit être
implémenter à la fin de toute les fonctionnalités »).

### Ce qui a été livré
- **`diff_chunks()`** (module `diff_service.py`, logique pure sans dépendance DB) :
  algorithme d'alignement documenté explicitement plutôt que laissé implicite —
  1) chunks de `content_hash` identique -> UNCHANGED (comparaison exacte, fiable,
  déjà calculée à l'ingestion, memoire.md §8) ; 2) parmi les chunks restants,
  appariement glouton par similarité textuelle décroissante
  (`difflib.SequenceMatcher`, stdlib — **aucune nouvelle dépendance**, §10) au-dessus
  d'un seuil de 0.6 -> MODIFIED ; 3) ce qui reste sans appariement -> ADDED/REMOVED.
- **`ChangeIntelligenceRepository`** : accès DB isolé (§9), résout automatiquement
  les deux dernières versions d'un document si `version_from`/`version_to` ne sont
  pas fournis explicitement (cas d'usage principal : « qu'est-ce qui a changé depuis
  la dernière mise à jour ? »).
- **`ImpactAnalysisService`** : à partir des chunks affectés (ajoutés/modifiés/
  supprimés) d'une comparaison, interroge le Knowledge Graph (nouvelle méthode
  `GraphStoreContract.find_entities_by_source_chunk_ids()`, ajoutée au contrat Phase
  4 sans casser les implémentations existantes — Protocol structurel, pas
  d'héritage strict) pour trouver les entités directement liées, puis leurs entités
  liées de proche en proche (impact indirect) via `get_related_entities()` déjà
  existant. Distingue explicitement impact direct/indirect plutôt que de tout
  fusionner (§18 : le graphe complète, il ne remplace pas).
- **Optionnalité assumée** : `ChangeIntelligenceService.analyze_impact()` renvoie
  `None` si aucun service d'impact n'est configuré — le diff reste utilisable seul
  si Neo4j n'est pas joignable (cohérent avec memoire.md §10 : le KG complète, il
  n'est pas indispensable).
- **API** : `POST /api/v1/change-intelligence/compare` (`document_id`,
  `version_from`/`version_to` optionnels, `include_impact` optionnel — défaut
  `true`).

### Tests et résultats
**159 tests, tous verts** (137 hérités des Phases 1-6 sans régression + 22
nouveaux : 7 sur `diff_chunks()` — y compris un cas garantissant qu'un chunk n'est
jamais apparié deux fois —, 4 sur `ImpactAnalysisService` avec un `GraphService`
factice, 6 d'intégration `ChangeIntelligenceService` contre un vrai PostgreSQL, 5
d'intégration API avec `Neo4jGraphStore` monkeypatché).

### Ce qui n'a volontairement pas été fait (hors périmètre Phase 7)
- Aucune notification automatique (email/Slack) aux équipes impactées — l'analyse
  d'impact renvoie une liste structurée, la notification serait une fonctionnalité
  distincte à demander explicitement (§3).
- Aucun stockage persistant de l'historique des comparaisons — chaque appel à
  `/compare` recalcule à la volée ; un historique nécessiterait un nouveau modèle de
  données, à signaler plutôt qu'à ajouter spontanément.
- Le seuil de similarité `MODIFICATION_SIMILARITY_THRESHOLD = 0.6` est une première
  estimation raisonnable (comme `CONFIDENCE_THRESHOLD` en Phase 6), non calibrée sur
  corpus réel — même statut provisoire, à ajuster en Phase 8 si les métriques le
  justifient.

### Limites héritées non résolues par cette phase
- Aucune requête Cypher réelle n'a jamais atteint un serveur Neo4j (limite Phase 4,
  §26) — `find_entities_by_source_chunk_ids()` est donc testée uniquement via un
  store en mémoire, jamais en conditions réelles.
- `CONFIDENCE_THRESHOLD` reste provisoire (Phase 6, §30).

### Prochaine étape
En attente d'instructions de Radda101. Options possibles : **Phase 8 — Évaluation**
(métriques sur corpus réel, qui permettrait aussi de recalibrer les seuils provisoires
`CONFIDENCE_THRESHOLD` et `MODIFICATION_SIMILARITY_THRESHOLD` en une seule passe), ou
vérification des limites Neo4j/reranker en attente depuis les Phases 4/6.

---

## 32. Bilan de la livraison Phase 8 — Évaluation (pas encore une clôture officielle)

**Statut : framework d'évaluation implémenté et testé. Radda101 a explicitement
autorisé de démarrer cette phase sans attendre la résolution des limites Neo4j
(Phase 4) et reranker (Phase 6) en cours — cette phase hérite donc mécaniquement de
ces deux limites non résolues, en plus des siennes propres.**

### Portée (rappel memoire.md §2 objectif 9)
« Évaluation scientifique comparative : LLM seul vs RAG classique vs Hybrid RAG vs
KG-RAG vs TEKIS complet, sur des métriques de retrieval, grounding, hallucination,
sécurité, abstention et performance. »

### Ce qui a été livré
- **5 variantes de pipeline** construites à partir des services déjà existants
  (aucune duplication de logique métier) :
  - `LLM_ONLY` : LLM sans aucun extrait fourni (baseline de comparaison).
  - `VECTOR_ONLY` : `RetrievalService` (Phase 2, vectoriel pur).
  - `HYBRID` : `HybridRetrievalService` (Phase 3, fusion + reranking).
  - `KG_RAG` : Hybrid + enrichissement du prompt par les entités du Knowledge
    Graph liées aux extraits retrouvés (nouveau : `build_graph_context_augmenter()`).
  - `TEKIS_COMPLETE` : Hybrid + KG + `ValidationService` (Phase 6 : confiance,
    contradictions, abstention).
- **Extension rétrocompatible** de `GenerationService`/`context_builder.py` :
  paramètre `context_augmenter` optionnel (défaut `None`), permettant l'injection
  du contexte KG sans toucher au comportement des Phases 2-6 — vérifié
  explicitement par deux tests dédiés (`test_generation_service_without_context_
  augmenter_unchanged` et la suite héritée, toutes deux vertes sans modification).
- **Métriques** (`metrics.py`, fonctions pures) : `precision_at_k`, `recall_at_k`,
  `reciprocal_rank` (retrieval) ; `keyword_coverage` (proxy lexical de
  grounding/hallucination — **limite assumée et documentée dans le code** : ce
  n'est pas une évaluation sémantique par juge LLM, seulement une présence de
  mots-clés) ; `abstention_correctness` ; `acl_leak_count` (sécurité — doit
  toujours valoir 0, vérifie qu'aucune source d'une version de document interdite
  n'atteint jamais les résultats).
- **`EvaluationRunner`** : orchestre l'exécution de chaque variante sur un jeu de
  questions et agrège les métriques (latence mesurée par variante/question).
- **API** : `POST /api/v1/evaluation/run` (protégée par authentification, comme
  `/chat`/`/search`), accepte un jeu de questions et une sélection optionnelle de
  variantes à comparer.

### Tests et résultats
**199 tests, tous verts** (159 hérités des Phases 1-7 sans régression + 40
nouveaux : 18 sur les métriques pures, 4 sur les adaptateurs de variantes, 4 sur
l'enrichisseur de contexte KG, 5 sur `EvaluationRunner`, 2 sur l'extension
`context_augmenter` de `GenerationService` — dont un qui vérifie explicitement la
non-régression du comportement par défaut —, 6 d'intégration API bout en bout avec
authentification réelle).

### Ce qui n'a volontairement pas été fait (hors périmètre de cette livraison)
- **Aucun jeu de données d'évaluation réel n'est fourni** : le framework attend un
  jeu de questions en entrée de l'API, mais aucun corpus annoté (questions +
  réponses attendues + chunks pertinents) n'a été construit sur des documents
  télécom réels — cela nécessite un travail humain de constitution de vérité
  terrain, hors périmètre du développement backend, à signaler pour discussion.
- **Aucun juge LLM** pour évaluer la véracité factuelle ou la qualité rédactionnelle
  des réponses — seul un proxy lexical (`keyword_coverage`) est implémenté. Un juge
  LLM introduirait sa propre incertitude (un LLM qui évalue un autre LLM) et un
  coût d'inférence supplémentaire — décision à prendre séparément, non tranchée
  spontanément ici.
- **Aucune génération de rapport pour l'article académique** (tableaux/graphiques
  comparatifs formatés) — l'API renvoie du JSON structuré, à transformer en
  tableaux pour l'article dans une étape éditoriale distincte (méthode en 7 étapes
  déjà établie pour la rédaction, memoire.md — approche & patterns).

### Limites héritées non résolues par cette phase
- `CONFIDENCE_THRESHOLD = 0.5` reste provisoire (Phase 6, §30) — les résultats de
  la variante `TEKIS_COMPLETE` en particulier doivent être interprétés avec cette
  réserve.
- Aucune requête Cypher n'a jamais atteint un serveur Neo4j réel (Phase 4, §26) —
  les variantes `KG_RAG`/`TEKIS_COMPLETE` tournent sans enrichissement KG effectif
  tant que cette vérification n'a pas eu lieu ; le code gère ce cas proprement
  (`graph_service` optionnel) plutôt que d'échouer, mais les métriques de ces deux
  variantes ne reflètent donc pour l'instant que l'absence d'enrichissement KG, pas
  sa présence.
- Aucun appel Ollama réel n'a eu lieu dans cet environnement (Phase 2, §23) — les
  métriques `keyword_coverage` obtenues avec les fakes de test sont illustratives
  du câblage, pas des résultats scientifiques exploitables.

**En clair : le framework d'évaluation est prêt et testé, mais aucune métrique
produite dans cet environnement de développement n'est scientifiquement
exploitable pour l'article — l'exécution réelle sur l'infrastructure de Radda101,
avec un jeu de questions annoté sur le vrai corpus télécom, reste nécessaire avant
toute utilisation des résultats dans l'article académique.**

### Prochaine étape
En attente d'instructions de Radda101. Suggestions possibles (à valider, pas
décidées ici) : constituer un jeu de questions d'évaluation annoté sur un
échantillon du corpus réel ; lancer l'évaluation sur l'infrastructure réelle
(Ollama + Neo4j + reranker) pour obtenir des métriques exploitables ; ou traiter en
parallèle les vérifications Phase 4/6 restées en attente.

---
