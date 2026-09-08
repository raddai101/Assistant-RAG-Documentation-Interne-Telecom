from pypdf import PdfReader

from app.modules.ingestion.contracts import ParsedDocument


class PdfParser:
    supported_extensions = (".pdf",)

    def parse(self, file_path: str) -> ParsedDocument:
        reader = PdfReader(file_path)
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n".join(pages_text)
        metadata = {
            "format": "pdf",
            "num_pages": len(reader.pages),
        }
        return ParsedDocument(text=full_text, pages=pages_text, metadata=metadata)
