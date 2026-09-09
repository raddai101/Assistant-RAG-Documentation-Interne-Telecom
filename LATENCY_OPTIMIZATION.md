# Optimisation de latence TEKIS — étape 1

Cette livraison vise d’abord à mesurer et supprimer les coûts répétés du pipeline RAG.

## Changements

- Le `GenerationService` est maintenant construit une seule fois par worker Flask/Gunicorn et conservé dans `current_app.extensions`.
- Le `HybridRetrievalService` de `/search` est également conservé entre les requêtes.
- Le `CrossEncoder` reste donc chargé en mémoire après sa première utilisation au lieu d’être recréé à chaque question.
- `HYBRID_CANDIDATE_K` passe de 50 à 20.
- `RETRIEVAL_TOP_K` passe de 10 à 5.
- Le nombre de workers Gunicorn passe à 1 par défaut pour éviter de charger plusieurs copies du CrossEncoder lourd dans une machine locale.
- Des mesures `[PERF]` sont ajoutées pour : ACL/temporalité, embedding, recherche vectorielle, recherche lexicale, reranking, validation, contexte graphe, prompt, LLM et durée totale.

## Déploiement

Depuis le dossier racine :

```powershell
docker compose build backend
docker compose up -d
```

Puis vérifier :

```powershell
docker ps
docker logs -f tekis-backend
```

Pose deux questions dans Tekis. La première peut rester plus lente car le CrossEncoder est chargé à froid. La seconde est la mesure importante pour vérifier que le chargement n’est plus répété.

## Ce qu’il faut observer

Les logs doivent contenir des lignes du type :

```text
[PERF] chat ACL+temporal: ...
[PERF] embedding query: ...
[PERF] recherche vectorielle: ...
[PERF] recherche lexicale: ...
[PERF] reranker: ...
[PERF] validation: ...
[PERF] graph context: ...
[PERF] prompt: ...
[PERF] LLM: ...
[PERF] génération totale: ...
[PERF] chat total: ...
```

La prochaine étape sera choisie à partir de ces mesures : optimisation du reranker, ACL/SQL, prompt/contexte, ou génération Ollama. Le streaming sera traité ensuite afin que la réponse commence à s’afficher avant la fin de la génération.
