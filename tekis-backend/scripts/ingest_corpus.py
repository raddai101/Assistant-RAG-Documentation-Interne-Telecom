"""Ingere le corpus local TEKIS puis laisse l'indexation vectorielle a l'API."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from werkzeug.datastructures import FileStorage

from app import create_app
from app.extensions import db
from app.models.document import DocumentVersion
from app.models.identity import Department
from app.modules.ingestion.quarantine import QuarantineManager
from app.modules.ingestion.service import IngestionService
from app.modules.ingestion.validation import FileValidationError

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt", ".xlsx"}


def get_or_create_department(name: str) -> Department:
    department = Department.query.filter_by(name=name).first()
    if department is None:
        department = Department(name=name)
        db.session.add(department)
        db.session.flush()
    return department


def ingest_corpus(corpus_dir: Path) -> tuple[int, int, int]:
    app = create_app("development")
    imported = skipped = rejected = 0
    with app.app_context():
        quarantine = QuarantineManager(app.config["QUARANTINE_DIR"])
        service = IngestionService(
            storage_dir=app.config["INGESTION_STORAGE_DIR"],
            quarantine_dir=app.config["QUARANTINE_DIR"],
            max_upload_size_mb=app.config["MAX_UPLOAD_SIZE_MB"],
            quarantine_manager=quarantine,
        )

        files = sorted(
            path for path in corpus_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        for path in files:
            checksum = service.compute_checksum(str(path))
            if DocumentVersion.query.filter_by(checksum=checksum).first() is not None:
                skipped += 1
                continue

            relative_parts = path.relative_to(corpus_dir).parts
            department_name = relative_parts[0] if len(relative_parts) > 1 else "Non classe"
            department = get_or_create_department(department_name)
            with path.open("rb") as source_stream:
                staged_path = quarantine.stage(
                    FileStorage(stream=source_stream, filename=path.name),
                    path.name,
                )
            try:
                service.ingest(
                    quarantine_file_path=staged_path,
                    original_filename=path.name,
                    title=path.stem,
                    department_id=department.id,
                    classification="enterprise",
                )
                imported += 1
                print(f"[OK] {path.relative_to(corpus_dir)}")
            except (FileValidationError, ValueError) as error:
                rejected += 1
                print(f"[REJECTED] {path.relative_to(corpus_dir)}: {error}")

        db.session.commit()
    return imported, skipped, rejected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default_corpus = Path(__file__).resolve().parents[2] / "corpus" / "enterprise"
    parser.add_argument("--corpus", type=Path, default=default_corpus)
    args = parser.parse_args()
    corpus_dir = args.corpus.resolve()
    if not corpus_dir.is_dir():
        raise SystemExit(f"Corpus introuvable : {corpus_dir}")

    imported, skipped, rejected = ingest_corpus(corpus_dir)
    print(f"Résumé : imported={imported}, skipped={skipped}, rejected={rejected}")


if __name__ == "__main__":
    main()
