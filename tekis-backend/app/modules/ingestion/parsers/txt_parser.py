from app.modules.ingestion.contracts import ParsedDocument


class TxtParser:
    supported_extensions = (".txt",)

    def parse(self, file_path: str) -> ParsedDocument:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return ParsedDocument(text=text, pages=[text], metadata={"format": "txt"})
