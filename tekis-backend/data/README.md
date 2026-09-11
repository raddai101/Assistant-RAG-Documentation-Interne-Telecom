# Dataset d'évaluation TEKIS

Une ligne JSONL par question. Pour les métriques Retrieval, renseigner `expected_chunk_ids` et idéalement `relevance_grades` (0–3). Pour citations/versions, renseigner `expected_citations` et `expected_document_version_ids`. Pour D/G, fournir `conversation_history`. Ne jamais mettre de données confidentielles inutiles dans le dataset.
