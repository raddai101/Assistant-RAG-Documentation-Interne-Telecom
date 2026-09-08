import io
import os

from werkzeug.datastructures import FileStorage

from app.modules.ingestion.quarantine import QuarantineManager


def test_stage_writes_file_into_quarantine_dir(tmp_path):
    manager = QuarantineManager(str(tmp_path / "quarantine"))
    upload = FileStorage(stream=io.BytesIO(b"contenu"), filename="doc.txt")

    path = manager.stage(upload, "doc.txt")

    assert os.path.exists(path)
    assert path.startswith(str(tmp_path / "quarantine"))
    assert path.endswith(".txt")


def test_release_moves_file_to_storage_dir(tmp_path):
    manager = QuarantineManager(str(tmp_path / "quarantine"))
    upload = FileStorage(stream=io.BytesIO(b"contenu"), filename="doc.txt")
    quarantine_path = manager.stage(upload, "doc.txt")

    final_path = manager.release(quarantine_path, str(tmp_path / "documents"))

    assert not os.path.exists(quarantine_path)
    assert os.path.exists(final_path)
    assert final_path.startswith(str(tmp_path / "documents"))


def test_reject_moves_file_to_rejected_with_reason(tmp_path):
    manager = QuarantineManager(str(tmp_path / "quarantine"))
    upload = FileStorage(stream=io.BytesIO(b"contenu"), filename="doc.txt")
    quarantine_path = manager.stage(upload, "doc.txt")

    rejected_path = manager.reject(quarantine_path, reason="signature invalide")

    assert not os.path.exists(quarantine_path)
    assert os.path.exists(rejected_path)
    assert "rejected" in rejected_path
    reason_content = open(rejected_path + ".reason.txt", encoding="utf-8").read()
    assert "signature invalide" in reason_content


def test_reject_on_missing_file_returns_none(tmp_path):
    manager = QuarantineManager(str(tmp_path / "quarantine"))
    result = manager.reject(str(tmp_path / "quarantine" / "inexistant.txt"), reason="n/a")
    assert result is None
