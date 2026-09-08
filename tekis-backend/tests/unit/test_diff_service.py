from app.modules.change_intelligence.diff_service import diff_chunks, ChunkForDiff
from app.modules.change_intelligence.contracts import ChangeType


def _chunk(chunk_id, content, content_hash=None):
    return ChunkForDiff(chunk_id=chunk_id, content=content, content_hash=content_hash or content)


def test_identical_chunks_are_unchanged():
    chunks_from = [_chunk(1, "Contenu stable identique")]
    chunks_to = [_chunk(2, "Contenu stable identique")]

    diffs = diff_chunks(chunks_from, chunks_to)

    assert len(diffs) == 1
    assert diffs[0].change_type == ChangeType.UNCHANGED
    assert diffs[0].chunk_id_from == 1
    assert diffs[0].chunk_id_to == 2


def test_similar_chunks_are_modified():
    chunks_from = [_chunk(1, "La procédure de maintenance dure deux heures.")]
    chunks_to = [_chunk(2, "La procédure de maintenance dure trois heures.")]

    diffs = diff_chunks(chunks_from, chunks_to)

    assert len(diffs) == 1
    assert diffs[0].change_type == ChangeType.MODIFIED
    assert diffs[0].chunk_id_from == 1
    assert diffs[0].chunk_id_to == 2
    assert diffs[0].similarity > 0.6


def test_completely_different_chunks_are_removed_and_added_separately():
    chunks_from = [_chunk(1, "Contenu totalement sans rapport avec la suite alpha bravo charlie.")]
    chunks_to = [_chunk(2, "Un sujet complètement différent xylophone kangourou nébuleuse.")]

    diffs = diff_chunks(chunks_from, chunks_to)

    change_types = {d.change_type for d in diffs}
    assert change_types == {ChangeType.REMOVED, ChangeType.ADDED}


def test_new_chunk_with_no_counterpart_is_added():
    diffs = diff_chunks([], [_chunk(1, "Nouveau contenu inédit.")])

    assert len(diffs) == 1
    assert diffs[0].change_type == ChangeType.ADDED
    assert diffs[0].chunk_id_to == 1
    assert diffs[0].chunk_id_from is None


def test_removed_chunk_with_no_counterpart_is_removed():
    diffs = diff_chunks([_chunk(1, "Ancien contenu disparu.")], [])

    assert len(diffs) == 1
    assert diffs[0].change_type == ChangeType.REMOVED
    assert diffs[0].chunk_id_from == 1
    assert diffs[0].chunk_id_to is None


def test_mixed_scenario_unchanged_modified_added_removed():
    chunks_from = [
        _chunk(1, "Section stable qui ne change jamais du tout."),
        _chunk(2, "La panne réseau dure environ dix minutes en moyenne."),
        _chunk(3, "Section obsolète à supprimer complètement du document source."),
    ]
    chunks_to = [
        _chunk(10, "Section stable qui ne change jamais du tout."),  # identique -> UNCHANGED
        _chunk(11, "La panne réseau dure environ vingt minutes en moyenne."),  # proche -> MODIFIED
        _chunk(12, "Toute nouvelle section ajoutée dans cette version du document."),  # -> ADDED
    ]

    diffs = diff_chunks(chunks_from, chunks_to)

    by_type = {t: [d for d in diffs if d.change_type == t] for t in ChangeType}
    assert len(by_type[ChangeType.UNCHANGED]) == 1
    assert len(by_type[ChangeType.MODIFIED]) == 1
    assert len(by_type[ChangeType.ADDED]) == 1
    assert len(by_type[ChangeType.REMOVED]) == 1
    assert by_type[ChangeType.REMOVED][0].chunk_id_from == 3


def test_each_chunk_matched_at_most_once():
    """Un chunk 'from' très proche de deux chunks 'to' ne doit être apparié qu'une
    seule fois (pas de double appariement)."""
    chunks_from = [_chunk(1, "Le serveur redémarre chaque nuit à minuit précis.")]
    chunks_to = [
        _chunk(2, "Le serveur redémarre chaque nuit à minuit pile."),
        _chunk(3, "Le serveur redémarre chaque nuit vers minuit environ."),
    ]

    diffs = diff_chunks(chunks_from, chunks_to)

    modified = [d for d in diffs if d.change_type == ChangeType.MODIFIED]
    added = [d for d in diffs if d.change_type == ChangeType.ADDED]
    assert len(modified) == 1
    assert len(added) == 1
