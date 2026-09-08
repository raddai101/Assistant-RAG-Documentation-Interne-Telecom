import io
import zipfile

import pytest

from app.modules.ingestion.validation import FileValidator, FileValidationError


@pytest.fixture
def validator():
    return FileValidator(max_size_mb=10)


def _write(tmp_path, name, content: bytes):
    path = tmp_path / name
    path.write_bytes(content)
    return str(path)


def test_valid_pdf_passes(tmp_path, validator):
    path = _write(tmp_path, "doc.pdf", b"%PDF-1.7\n%contenu simplifie")
    result = validator.validate(path, "doc.pdf")
    assert result.detected_mime == "application/pdf"


def test_txt_disguised_as_pdf_is_rejected(tmp_path, validator):
    path = _write(tmp_path, "faux.pdf", b"Juste du texte, pas un PDF.")
    with pytest.raises(FileValidationError, match="PDF"):
        validator.validate(path, "faux.pdf")


def test_valid_txt_passes(tmp_path, validator):
    path = _write(tmp_path, "note.txt", "Contenu télécom en clair.".encode("utf-8"))
    result = validator.validate(path, "note.txt")
    assert result.detected_mime == "text/plain"


def test_binary_disguised_as_txt_is_rejected(tmp_path, validator):
    path = _write(tmp_path, "faux.txt", b"\x00\x01\x02binaire\x00")
    with pytest.raises(FileValidationError, match="binaire|nuls"):
        validator.validate(path, "faux.txt")


def test_empty_file_is_rejected(tmp_path, validator):
    path = _write(tmp_path, "vide.txt", b"")
    with pytest.raises(FileValidationError, match="vide"):
        validator.validate(path, "vide.txt")


def test_oversized_file_is_rejected(tmp_path):
    small_validator = FileValidator(max_size_mb=1)
    path = _write(tmp_path, "gros.txt", b"A" * (2 * 1024 * 1024))
    with pytest.raises(FileValidationError, match="volumineux"):
        small_validator.validate(path, "gros.txt")


def test_docx_without_word_structure_is_rejected(tmp_path, validator):
    # ZIP valide mais sans la structure interne attendue d'un .docx
    path = tmp_path / "faux.docx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("random.txt", "contenu quelconque")
    with pytest.raises(FileValidationError, match="fichier interne"):
        validator.validate(str(path), "faux.docx")


def test_non_zip_disguised_as_docx_is_rejected(tmp_path, validator):
    path = _write(tmp_path, "faux.docx", b"pas du tout un zip")
    with pytest.raises(FileValidationError, match="ZIP"):
        validator.validate(path, "faux.docx")


def test_unsupported_extension_is_rejected(tmp_path, validator):
    path = _write(tmp_path, "schema.dwg", b"binaire quelconque")
    with pytest.raises(FileValidationError, match="non supportée"):
        validator.validate(path, "schema.dwg")
