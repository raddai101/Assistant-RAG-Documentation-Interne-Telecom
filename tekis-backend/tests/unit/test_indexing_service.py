import pytest

from app import create_app
from app.extensions import db
from app.models.document import Document, DocumentVersion, DocumentStatus
from app.models.chunk import Chunk, ChunkEmbeddingMeta
from app.modules.retrieval.indexing_service import EmbeddingIndexingService
from app.modules.retrieval.repository import RetrievalRepository
from app.modules.retrieval.vector.chroma_store import ChromaVectorStore


class FakeEmbeddingClient:
    """Vecteur déterministe = [longueur du texte] pour vérifier l'association
    chunk -> vecteur sans dépendre d'un vrai modèle."""

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [[float(len(t))] for t in texts]


class WrongCountEmbeddingClient:
    def embed(self, texts):
        return [[0.0]]  # toujours 1 vecteur, quel que soit le nombre de textes


@pytest.fixture
def app_context(tmp_path):
    app = create_app("testing")
    app.config["CHROMA_PERSIST_DIR"] = str(tmp_path / "chroma")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _make_document_with_chunks(num_chunks=2):
    document = Document(title="Procédure test")
    db.session.add(document)
    db.session.flush()
    version = DocumentVersion(
        document_id=document.id,
        version=1,
        status=DocumentStatus.ACTIVE,
        storage_path="/tmp/fake.txt",
        original_filename="fake.txt",
        file_type="txt",
    )
    db.session.add(version)
    db.session.flush()
    chunks = []
    for i in range(num_chunks):
        chunk = Chunk(
            document_version_id=version.id,
            content=f"contenu du chunk {i}",
            position=i,
            content_hash=f"hash{i}",
            page=1,
        )
        db.session.add(chunk)
        chunks.append(chunk)
    db.session.commit()
    return document, version, chunks


def test_index_pending_chunks_embeds_and_stores_in_chroma(app_context, tmp_path):
    _, version, chunks = _make_document_with_chunks(2)
    embedding_client = FakeEmbeddingClient()
    vector_store = ChromaVectorStore(
        persist_dir=str(tmp_path / "chroma2"), collection_name="test"
    )
    service = EmbeddingIndexingService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        embedding_model_name="fake-model",
        repository=RetrievalRepository(),
    )

    result = service.index_pending_chunks()

    assert result.num_chunks_indexed == 2
    for chunk in chunks:
        db.session.refresh(chunk)
        assert chunk.embedding_meta is not None
        assert chunk.embedding_meta.embedding_model == "fake-model"
        assert chunk.embedding_meta.chroma_id == f"chunk-{chunk.id}"

    stored = vector_store.get([f"chunk-{c.id}" for c in chunks])
    assert len(stored) == 2


def test_index_pending_chunks_skips_already_indexed(app_context, tmp_path):
    _, version, chunks = _make_document_with_chunks(1)
    embedding_client = FakeEmbeddingClient()
    vector_store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma3"), collection_name="test")
    service = EmbeddingIndexingService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        embedding_model_name="fake-model",
    )

    first = service.index_pending_chunks()
    second = service.index_pending_chunks()

    assert first.num_chunks_indexed == 1
    assert second.num_chunks_indexed == 0  # rien à ré-indexer
    assert len(embedding_client.calls) == 1


def test_index_pending_chunks_filters_by_document_version(app_context, tmp_path):
    _, version_a, chunks_a = _make_document_with_chunks(1)
    _, version_b, chunks_b = _make_document_with_chunks(1)
    embedding_client = FakeEmbeddingClient()
    vector_store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma4"), collection_name="test")
    service = EmbeddingIndexingService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        embedding_model_name="fake-model",
    )

    result = service.index_pending_chunks(document_version_id=version_a.id)

    assert result.num_chunks_indexed == 1
    db.session.refresh(chunks_a[0])
    db.session.refresh(chunks_b[0])
    assert chunks_a[0].embedding_meta is not None
    assert chunks_b[0].embedding_meta is None


def test_index_pending_chunks_returns_zero_when_nothing_to_index(app_context, tmp_path):
    embedding_client = FakeEmbeddingClient()
    vector_store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma5"), collection_name="test")
    service = EmbeddingIndexingService(
        embedding_client=embedding_client,
        vector_store=vector_store,
        embedding_model_name="fake-model",
    )

    result = service.index_pending_chunks()

    assert result.num_chunks_indexed == 0
    assert embedding_client.calls == []


def test_save_embedding_meta_is_idempotent(app_context):
    _, version, chunks = _make_document_with_chunks(1)
    repository = RetrievalRepository()

    first = repository.save_embedding_meta(chunks[0], "bge-m3", 1024, "chunk-1")
    second = repository.save_embedding_meta(chunks[0], "bge-m3", 1024, "chunk-1")
    repository.commit()

    assert first.chunk_id == second.chunk_id == chunks[0].id
    assert ChunkEmbeddingMeta.query.count() == 1


def test_index_pending_chunks_raises_and_rolls_back_on_vector_count_mismatch(app_context, tmp_path):
    _, version, chunks = _make_document_with_chunks(2)
    vector_store = ChromaVectorStore(persist_dir=str(tmp_path / "chroma6"), collection_name="test")
    service = EmbeddingIndexingService(
        embedding_client=WrongCountEmbeddingClient(),
        vector_store=vector_store,
        embedding_model_name="fake-model",
    )

    with pytest.raises(ValueError, match="nombre de vecteurs"):
        service.index_pending_chunks()

    db.session.refresh(chunks[0])
    assert chunks[0].embedding_meta is None  # rien n'a été persisté
