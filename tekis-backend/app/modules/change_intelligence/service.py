"""
Service d'orchestration du module `change_intelligence` (Phase 7), point d'entrée
unique pour la route API (§9). Combine récupération des versions (repository) ->
alignement V(n-1)/V(n) (`diff_service`) -> analyse d'impact via le Knowledge Graph
(`impact_service`, optionnelle).
"""
from app.modules.change_intelligence.contracts import VersionComparisonResult, ImpactAnalysisResult
from app.modules.change_intelligence.diff_service import diff_chunks
from app.modules.change_intelligence.repository import (
    ChangeIntelligenceRepository,
    DocumentVersionNotFoundError,
)
from app.modules.change_intelligence.impact_service import ImpactAnalysisService


class ChangeIntelligenceService:
    def __init__(
        self,
        repository: ChangeIntelligenceRepository,
        impact_service: ImpactAnalysisService | None = None,
    ):
        self._repository = repository
        self._impact_service = impact_service

    def compare_versions(
        self,
        document_id: int,
        version_from: int | None = None,
        version_to: int | None = None,
    ) -> VersionComparisonResult:
        """
        Si `version_from`/`version_to` ne sont pas fournis, compare automatiquement
        les deux dernières versions du document (cas d'usage principal : « qu'est-ce
        qui a changé depuis la dernière mise à jour ? »).
        """
        document = self._repository.get_document(document_id)
        if document is None:
            raise DocumentVersionNotFoundError(f"Document id={document_id} introuvable.")

        if version_from is None or version_to is None:
            pair = self._repository.get_latest_two_versions(document_id)
            if pair is None:
                raise DocumentVersionNotFoundError(
                    f"Le document id={document_id} a moins de deux versions : "
                    f"aucune comparaison possible."
                )
            dv_from, dv_to = pair
        else:
            dv_from = self._repository.get_version(document_id, version_from)
            dv_to = self._repository.get_version(document_id, version_to)
            if dv_from is None:
                raise DocumentVersionNotFoundError(f"Version {version_from} introuvable pour ce document.")
            if dv_to is None:
                raise DocumentVersionNotFoundError(f"Version {version_to} introuvable pour ce document.")

        chunks_from = self._repository.get_chunks_for_version(dv_from.id)
        chunks_to = self._repository.get_chunks_for_version(dv_to.id)
        diffs = diff_chunks(chunks_from, chunks_to)

        return VersionComparisonResult(
            document_id=document_id,
            version_from=dv_from.version,
            version_to=dv_to.version,
            diffs=diffs,
        )

    def analyze_impact(self, comparison: VersionComparisonResult) -> ImpactAnalysisResult | None:
        """Renvoie None si le service d'analyse d'impact n'est pas configuré (le
        Knowledge Graph est optionnel — memoire.md §10 : il complète, il n'est pas
        indispensable au fonctionnement du diff lui-même)."""
        if self._impact_service is None:
            return None

        affected_chunk_ids = [
            cid
            for diff in comparison.diffs
            if diff.change_type.value != "unchanged"
            for cid in (diff.chunk_id_from, diff.chunk_id_to)
            if cid is not None
        ]
        return self._impact_service.analyze(affected_chunk_ids)
