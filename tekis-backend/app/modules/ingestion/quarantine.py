"""
Gestion de la quarantaine des fichiers uploadés (dernière étape de la Phase 1,
memoire.md §8).

Règle : aucun fichier uploadé n'est écrit directement dans `INGESTION_STORAGE_DIR`.
Il est d'abord mis en quarantaine (`stage`), puis :
- si `FileValidator` le valide, il est déplacé vers le stockage définitif (`release`) ;
- sinon, il est déplacé vers `quarantaine/rejected/` avec un motif tracé (`reject`),
  jamais supprimé silencieusement (cohérent avec §14 : ne jamais masquer une erreur).
"""
import os
import shutil
import uuid
from datetime import datetime, timezone


class QuarantineManager:
    def __init__(self, quarantine_dir: str):
        self._quarantine_dir = quarantine_dir
        self._rejected_dir = os.path.join(quarantine_dir, "rejected")
        os.makedirs(self._quarantine_dir, exist_ok=True)
        os.makedirs(self._rejected_dir, exist_ok=True)

    def stage(self, file_storage, original_filename: str) -> str:
        """Écrit le flux uploadé directement en quarantaine. Retourne le chemin."""
        ext = os.path.splitext(original_filename)[1].lower()
        quarantine_path = os.path.join(self._quarantine_dir, f"{uuid.uuid4().hex}{ext}")
        file_storage.save(quarantine_path)
        return quarantine_path

    def release(self, quarantine_path: str, storage_dir: str) -> str:
        """Déplace un fichier validé de la quarantaine vers le stockage définitif."""
        os.makedirs(storage_dir, exist_ok=True)
        ext = os.path.splitext(quarantine_path)[1]
        final_path = os.path.join(storage_dir, f"{uuid.uuid4().hex}{ext}")
        shutil.move(quarantine_path, final_path)
        return final_path

    def reject(self, quarantine_path: str, reason: str) -> str | None:
        """Déplace un fichier rejeté vers `quarantine/rejected/` avec un fichier
        `.reason.txt` documentant le motif, pour audit (jamais de suppression
        silencieuse)."""
        if not os.path.exists(quarantine_path):
            return None
        basename = os.path.basename(quarantine_path)
        rejected_path = os.path.join(self._rejected_dir, basename)
        shutil.move(quarantine_path, rejected_path)

        timestamp = datetime.now(timezone.utc).isoformat()
        with open(rejected_path + ".reason.txt", "w", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Rejeté : {reason}\n")
        return rejected_path
