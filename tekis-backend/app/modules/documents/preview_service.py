"""Prévisualisation sécurisée des versions documentaires.

Le service réutilise les mêmes parsers que l'ingestion afin que l'aperçu
présente le contenu réellement stocké et non une copie indépendante.
"""
from pathlib import Path

from app.modules.ingestion.parsers import get_parser_for


class DocumentPreviewError(ValueError):
    """Levée lorsqu'une version ne peut pas être prévisualisée."""


class DocumentPreviewService:
    MAX_PREVIEW_CHARS = 250_000

    def preview(self, version) -> dict:
        storage_path = Path(version.storage_path)
        if not storage_path.is_file():
            raise DocumentPreviewError("Le fichier source du document est introuvable dans le stockage.")

        parser = get_parser_for(version.original_filename or str(storage_path))
        parsed = parser.parse(str(storage_path))
        pages = parsed.pages or [parsed.text]

        total_chars = sum(len(page or "") for page in pages)
        remaining = self.MAX_PREVIEW_CHARS
        preview_pages = []
        truncated = False

        for index, page in enumerate(pages, start=1):
            text = (page or "").strip()
            if not text:
                preview_pages.append({"page": index, "content": ""})
                continue

            if len(text) > remaining:
                text = text[:remaining].rstrip()
                truncated = True

            preview_pages.append({"page": index, "content": text})
            remaining -= len(text)
            if remaining <= 0:
                truncated = True
                break

        return {
            "document_id": version.document_id,
            "document_version_id": version.id,
            "version": version.version,
            "title": version.document.title if version.document else None,
            "original_filename": version.original_filename,
            "file_type": version.file_type,
            "pages": preview_pages,
            "total_pages": len(pages),
            "total_characters": total_chars,
            "truncated": truncated,
        }
