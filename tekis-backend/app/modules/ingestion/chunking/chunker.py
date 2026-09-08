from app.modules.ingestion.contracts import ParsedDocument, ChunkResult


class FixedSizeChunker:
    """
    Chunker de référence : découpe chaque page/section en fenêtres de taille fixe avec
    chevauchement, sans dépasser les frontières de page (pour conserver page/section
    dans les métadonnées du chunk, utile au Change Intelligence et aux citations).

    Choix des tailles par défaut : à valider/affiner en Phase 2 selon le comportement
    réel du retrieval sur le corpus télécom (non encore mesuré).
    """

    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        if overlap >= chunk_size:
            raise ValueError("`overlap` doit être strictement inférieur à `chunk_size`.")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, parsed: ParsedDocument) -> list[ChunkResult]:
        results: list[ChunkResult] = []
        position = 0
        pages = parsed.pages or [parsed.text]

        for page_number, page_text in enumerate(pages, start=1):
            page_text = page_text.strip()
            if not page_text:
                continue

            start = 0
            while start < len(page_text):
                end = min(start + self.chunk_size, len(page_text))
                content = page_text[start:end].strip()
                if content:
                    results.append(
                        ChunkResult(content=content, position=position, page=page_number)
                    )
                    position += 1
                if end == len(page_text):
                    break
                start = end - self.overlap

        return results
