"""
Détection de contradictions (module `validation`, Phase 6, memoire.md §14).

Portée volontairement limitée à des signaux **structurels/métadonnée**
(version/statut/date — cf. memoire.md §14), PAS une analyse sémantique du contenu
des chunks (qui nécessiterait un appel LLM supplémentaire, non demandé — memoire.md
§29). Si Radda101 souhaite une détection sémantique de contradiction de contenu, ce
sera signalé et proposé séparément (§3 des instructions), pas ajouté silencieusement.

Signal détecté ici : plusieurs versions d'un même document apparaissent
simultanément dans les résultats retenus. Cela ne devrait jamais arriver puisque
`TemporalResolver` (Phase 5) ne retient qu'une version valide par document — ce
détecteur est un garde-fou défensif, pas une confiance aveugle dans l'étage
précédent (défense en profondeur, même logique que la double validation taille/
signature de la Phase 1).
"""
from app.modules.retrieval.contracts import VectorSearchResult
from app.modules.validation.repository import ValidationRepository


class ContradictionDetector:
    def __init__(self, repository: ValidationRepository | None = None):
        self._repository = repository or ValidationRepository()

    def detect(self, results: list[VectorSearchResult]) -> list[str]:
        version_ids = [
            r.metadata.get("document_version_id")
            for r in results
            if r.metadata.get("document_version_id") is not None
        ]
        if not version_ids:
            return []

        versions = self._repository.get_document_versions(version_ids)
        versions_by_document: dict[int, set[int]] = {}
        for v in versions:
            versions_by_document.setdefault(v.document_id, set()).add(v.id)

        warnings = []
        for document_id, ids in versions_by_document.items():
            if len(ids) > 1:
                warnings.append(
                    f"Plusieurs versions du document {document_id} sont présentes "
                    f"simultanément dans les preuves retenues (versions {sorted(ids)}) "
                    f"— incohérence temporelle inattendue, à examiner."
                )
        return warnings
