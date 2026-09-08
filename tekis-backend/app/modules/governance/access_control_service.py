"""
Service de contrôle d'accès (module `governance`, Phase 5, memoire.md §12/§15).

Politique retenue, à confirmer par Radda101 (§24 des instructions : ne pas inventer
silencieusement une politique de sécurité) :
- **Default-deny explicite.** Une version de document SANS aucune ligne
  `Permission` associée (ni au niveau document, ni au niveau version) n'est
  accessible à PERSONNE, y compris un utilisateur authentifié — tant qu'aucun droit
  n'a été explicitement accordé, le document n'existe pas pour le retrieval. C'est la
  posture la plus sûre pour un système d'accès conditionné (§15), mais elle implique
  que **tout document ingéré doit recevoir une `Permission` explicite pour devenir
  interrogeable** via `/search` ou `/chat`.
- **Bypass rôle admin.** Un utilisateur dont `role.name` est dans
  `ADMIN_ROLE_NAMES` (config, défaut `{"admin"}`) voit tout le corpus, sans avoir à
  lister chaque document — nécessaire ne serait-ce que pour l'exploitation/l'audit.
  Ce nom de rôle est configurable, pas codé en dur en dehors de la config.
"""
from app.modules.governance.repository import GovernanceRepository


class AccessControlService:
    def __init__(
        self,
        repository: GovernanceRepository | None = None,
        admin_role_names: frozenset[str] = frozenset({"admin"}),
    ):
        self._repository = repository or GovernanceRepository()
        self._admin_role_names = admin_role_names

    def get_authorized_document_version_ids(self, user) -> set[int] | None:
        """Renvoie l'ensemble des `document_version_id` autorisés pour `user`, ou
        `None` pour signifier « accès illimité » (rôle admin) — jamais `None` pour
        signifier autre chose, afin de ne jamais confondre « pas de restriction »
        avec « aucun résultat »."""
        role_name = user.role.name if user.role else None
        if role_name in self._admin_role_names:
            return None

        authorized_ids: set[int] = set()
        for version in self._repository.get_all_document_versions():
            permissions = self._repository.get_permissions_for_document(
                document_id=version.document_id, document_version_id=version.id
            )
            if not permissions:
                continue  # default-deny : aucune permission -> aucun accès
            if any(self._permission_matches(p, user) for p in permissions):
                authorized_ids.add(version.id)
        return authorized_ids

    @staticmethod
    def _permission_matches(permission, user) -> bool:
        if user.id in (permission.allowed_users or []):
            return True
        if user.role and user.role.name in (permission.allowed_roles or []):
            return True
        if user.department_id is not None and user.department_id in (
            permission.allowed_departments or []
        ):
            return True
        return False
