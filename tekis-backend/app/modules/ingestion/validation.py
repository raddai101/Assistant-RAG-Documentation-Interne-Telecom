"""
Validation de fichiers avant intégration au corpus (dernière étape de la Phase 1,
memoire.md §8).

Choix technique : la vérification du type réel du contenu se fait par inspection de
signature (magic bytes / structure interne), en pure stdlib (`zipfile`), plutôt que
via `python-magic` (qui nécessite la librairie système `libmagic`). Ce choix évite
une dépendance supplémentaire non indispensable (§10 des instructions : « éviter les
dépendances inutiles ») tout en couvrant l'objectif recherché : détecter une extension
trompeuse (ex. un exécutable renommé en `.pdf`).

Pipeline appelant (voir `service.py`) :
    upload -> quarantaine -> FileValidator.validate() -> si conforme, déplacement
    vers le stockage définitif ; si non conforme, `FileValidationError` levée et le
    fichier reste en quarantaine (rejeté par `QuarantineManager.reject`).
"""
import os
import zipfile
from dataclasses import dataclass


class FileValidationError(ValueError):
    """Levée quand un fichier ne passe pas la validation de sécurité de la Phase 1."""


EXPECTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
}

# Garde-fous anti zip-bomb pour les formats basés sur ZIP (docx, xlsx). Valeurs
# volontairement larges pour ne pas rejeter des documents télécom légitimes
# volumineux — à ajuster en Phase 2 si le corpus réel le justifie.
MAX_ZIP_UNCOMPRESSED_MB = 500
MAX_ZIP_ENTRIES = 10_000


@dataclass
class ValidationResult:
    detected_mime: str
    size_bytes: int


class FileValidator:
    def __init__(self, max_size_mb: int):
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def validate(self, file_path: str, original_filename: str) -> ValidationResult:
        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in EXPECTED_MIME_TYPES:
            raise FileValidationError(
                f"Extension '{ext}' non supportée en Phase 1 (formats acceptés : "
                f"PDF, DOCX, XLSX, TXT)."
            )

        size_bytes = self._check_size(file_path)
        detected_mime = self._detect_and_check_mime(file_path, ext)

        return ValidationResult(detected_mime=detected_mime, size_bytes=size_bytes)

    def _check_size(self, file_path: str) -> int:
        size_bytes = os.path.getsize(file_path)
        if size_bytes == 0:
            raise FileValidationError("Fichier vide.")
        if size_bytes > self.max_size_bytes:
            raise FileValidationError(
                f"Fichier trop volumineux ({size_bytes / (1024 * 1024):.1f} Mo, "
                f"max {self.max_size_bytes / (1024 * 1024):.0f} Mo)."
            )
        return size_bytes

    def _detect_and_check_mime(self, file_path: str, ext: str) -> str:
        checker = {
            ".pdf": self._check_pdf,
            ".docx": lambda p: self._check_office_zip(p, "word/document.xml", ext),
            ".xlsx": lambda p: self._check_office_zip(p, "xl/workbook.xml", ext),
            ".txt": self._check_txt,
        }[ext]
        return checker(file_path)

    def _check_pdf(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            raise FileValidationError(
                "Le contenu du fichier ne correspond pas à un PDF valide (signature "
                "'%PDF-' absente) — extension trompeuse ou fichier corrompu."
            )
        return EXPECTED_MIME_TYPES[".pdf"]

    def _check_office_zip(self, file_path: str, required_member: str, expected_ext: str) -> str:
        if not zipfile.is_zipfile(file_path):
            raise FileValidationError(
                f"Le contenu du fichier ne correspond pas à un document Office "
                f"'{expected_ext}' valide (structure ZIP absente) — extension "
                f"trompeuse ou fichier corrompu."
            )
        with zipfile.ZipFile(file_path) as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise FileValidationError(
                    "Fichier rejeté : nombre d'entrées internes anormalement élevé "
                    "(protection anti zip-bomb)."
                )
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_MB * 1024 * 1024:
                raise FileValidationError(
                    "Fichier rejeté : taille décompressée anormalement élevée "
                    "(protection anti zip-bomb)."
                )
            if required_member not in zf.namelist():
                raise FileValidationError(
                    f"Le contenu du fichier ne correspond pas à un document "
                    f"'{expected_ext}' valide (fichier interne '{required_member}' "
                    f"absent) — extension trompeuse ou fichier corrompu."
                )
        return EXPECTED_MIME_TYPES[expected_ext]

    def _check_txt(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            sample = f.read(8192)
        if b"\x00" in sample:
            raise FileValidationError(
                "Le contenu du fichier ne correspond pas à un fichier texte valide "
                "(octets nuls détectés) — extension trompeuse ou fichier binaire."
            )
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            raise FileValidationError(
                "Le contenu du fichier ne correspond pas à un fichier texte UTF-8 "
                "valide."
            )
        return EXPECTED_MIME_TYPES[".txt"]
