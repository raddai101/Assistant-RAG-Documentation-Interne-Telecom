"""
Résolution temporelle (module `governance`, Phase 5, memoire.md §11/§16). La
sélection de la version applicable à une date donnée est effectuée ICI, par le
backend, jamais déléguée au LLM (§16 des instructions — règle non négociable).

Règle de résolution, par document, pour une date `as_of` donnée :
1. Si au moins une version a `valid_from`/`valid_to` renseignés et que
   `valid_from <= as_of <= (valid_to ou +infini)`, c'est cette version qui est
   retenue (celle avec le `valid_from` le plus récent si plusieurs se chevauchent —
   cas anormal, mais on choisit la plus récente plutôt que de planter).
2. Sinon (aucune version temporellement renseignée pour ce document — cas courant
   en Phase 1/2, `valid_from`/`valid_to` restés inexploités), on retombe sur le
   statut : la version `ACTIVE` est retenue. C'est le comportement de fait déjà en
   place depuis la Phase 1 (memoire.md §22), ici rendu explicite plutôt qu'implicite.
"""
from datetime import datetime, timezone

from app.models.document import DocumentStatus
from app.modules.governance.repository import GovernanceRepository


class TemporalResolver:
    def __init__(self, repository: GovernanceRepository | None = None):
        self._repository = repository or GovernanceRepository()

    def get_valid_document_version_ids(self, as_of: datetime | None = None) -> set[int]:
        as_of = as_of or datetime.now(timezone.utc)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        versions_by_document: dict[int, list] = {}
        for version in self._repository.get_all_document_versions():
            versions_by_document.setdefault(version.document_id, []).append(version)

        valid_ids: set[int] = set()
        for versions in versions_by_document.values():
            temporally_defined = [v for v in versions if v.valid_from is not None]
            if temporally_defined:
                candidates = [
                    v
                    for v in temporally_defined
                    if self._within_range(v, as_of)
                ]
                if candidates:
                    chosen = max(candidates, key=lambda v: v.valid_from)
                    valid_ids.add(chosen.id)
                continue

            # Repli : pas de temporalité fine renseignée -> statut ACTIVE.
            for v in versions:
                if v.status == DocumentStatus.ACTIVE:
                    valid_ids.add(v.id)

        return valid_ids

    @staticmethod
    def _within_range(version, as_of: datetime) -> bool:
        valid_from = version.valid_from
        if valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)
        if valid_from > as_of:
            return False
        if version.valid_to is None:
            return True
        valid_to = version.valid_to
        if valid_to.tzinfo is None:
            valid_to = valid_to.replace(tzinfo=timezone.utc)
        return as_of <= valid_to
