from app.modules.ingestion.contracts import ParsedDocument
from app.modules.ingestion.chunking.chunker import FixedSizeChunker


def test_chunker_splits_text_with_overlap():
    text = "A" * 1000
    parsed = ParsedDocument(text=text, pages=[text], metadata={})
    chunker = FixedSizeChunker(chunk_size=400, overlap=50)

    chunks = chunker.chunk(parsed)

    assert len(chunks) == 3
    assert all(len(c.content) <= 400 for c in chunks)
    assert chunks[0].page == 1
    assert [c.position for c in chunks] == [0, 1, 2]


def test_chunker_rejects_overlap_gte_chunk_size():
    try:
        FixedSizeChunker(chunk_size=100, overlap=100)
        assert False, "devrait lever ValueError"
    except ValueError:
        pass


def test_chunker_skips_empty_pages():
    parsed = ParsedDocument(text="", pages=["", "   ", "contenu réel"], metadata={})
    chunker = FixedSizeChunker(chunk_size=400, overlap=50)

    chunks = chunker.chunk(parsed)

    assert len(chunks) == 1
    assert chunks[0].content == "contenu réel"
    assert chunks[0].page == 3
