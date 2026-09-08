import os

from app.modules.ingestion.parsers.pdf_parser import PdfParser
from app.modules.ingestion.parsers.docx_parser import DocxParser
from app.modules.ingestion.parsers.xlsx_parser import XlsxParser
from app.modules.ingestion.parsers.txt_parser import TxtParser

_PARSERS = [PdfParser(), DocxParser(), XlsxParser(), TxtParser()]


class UnsupportedFileTypeError(ValueError):
    pass


def get_parser_for(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    for parser in _PARSERS:
        if ext in parser.supported_extensions:
            return parser
    raise UnsupportedFileTypeError(
        f"Aucun parser disponible pour l'extension '{ext}'. "
        f"Formats supportés (Phase 1) : PDF, DOCX, XLSX, TXT."
    )
