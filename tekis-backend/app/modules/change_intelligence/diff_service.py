"""
Alignement de deux ensembles de chunks (V(n-1) et V(n) d'un même document) et
détection ajouts/suppressions/modifications (memoire.md §15).

Logique pure (aucun accès DB ici — voir `repository.py` pour la récupération des
chunks) : facilite les tests et le remplacement futur de l'algorithme d'alignement
sans toucher au reste du système (§3.1 « CHANGE IMPLEMENTATION, PRESERVE CONTRACT »).

Algorithme d'alignement (choix délibéré, documenté plutôt que laissé implicite) :
1. Les chunks dont `content_hash` est identique entre V(n-1) et V(n) sont UNCHANGED
   (comparaison exacte, fiable, déjà calculée à l'ingestion — memoire.md §8).
2. Parmi les chunks restants, on tente d'apparier les paires les plus textuellement
   proches (`difflib.SequenceMatcher`, stdlib — pas de nouvelle dépendance, §10) au-
   dessus d'un seuil de similarité : ces paires sont MODIFIED.
3. Ce qui reste sans appariement côté V(n-1) est REMOVED ; côté V(n) est ADDED.
"""
from difflib import SequenceMatcher

from app.modules.change_intelligence.contracts import ChunkDiff, ChangeType

MODIFICATION_SIMILARITY_THRESHOLD = 0.6


class ChunkForDiff:
    """Vue minimale d'un chunk nécessaire au diff — découple ce module du modèle
    SQLAlchemy `Chunk` (le repository fait la conversion, §9)."""

    def __init__(self, chunk_id: int, content: str, content_hash: str):
        self.chunk_id = chunk_id
        self.content = content
        self.content_hash = content_hash


def diff_chunks(chunks_from: list[ChunkForDiff], chunks_to: list[ChunkForDiff]) -> list[ChunkDiff]:
    diffs: list[ChunkDiff] = []

    hashes_from = {c.content_hash: c for c in chunks_from}
    hashes_to = {c.content_hash: c for c in chunks_to}

    unchanged_hashes = set(hashes_from) & set(hashes_to)
    for h in unchanged_hashes:
        diffs.append(
            ChunkDiff(
                change_type=ChangeType.UNCHANGED,
                chunk_id_from=hashes_from[h].chunk_id,
                chunk_id_to=hashes_to[h].chunk_id,
                content_from=hashes_from[h].content,
                content_to=hashes_to[h].content,
            )
        )

    remaining_from = [c for c in chunks_from if c.content_hash not in unchanged_hashes]
    remaining_to = [c for c in chunks_to if c.content_hash not in unchanged_hashes]

    matched_from_ids: set[int] = set()
    matched_to_ids: set[int] = set()

    # Appariement glouton par similarité décroissante : simple et suffisant pour la
    # taille de corpus attendue par chunk (quelques dizaines à centaines par
    # document) — à revoir si le volume réel impose un algorithme plus efficace
    # (Phase 8, si les métriques le justifient).
    candidate_pairs = []
    for c_from in remaining_from:
        for c_to in remaining_to:
            ratio = SequenceMatcher(None, c_from.content, c_to.content).ratio()
            if ratio >= MODIFICATION_SIMILARITY_THRESHOLD:
                candidate_pairs.append((ratio, c_from, c_to))
    candidate_pairs.sort(key=lambda p: p[0], reverse=True)

    for ratio, c_from, c_to in candidate_pairs:
        if c_from.chunk_id in matched_from_ids or c_to.chunk_id in matched_to_ids:
            continue
        matched_from_ids.add(c_from.chunk_id)
        matched_to_ids.add(c_to.chunk_id)
        diffs.append(
            ChunkDiff(
                change_type=ChangeType.MODIFIED,
                chunk_id_from=c_from.chunk_id,
                chunk_id_to=c_to.chunk_id,
                content_from=c_from.content,
                content_to=c_to.content,
                similarity=ratio,
            )
        )

    for c_from in remaining_from:
        if c_from.chunk_id not in matched_from_ids:
            diffs.append(
                ChunkDiff(
                    change_type=ChangeType.REMOVED,
                    chunk_id_from=c_from.chunk_id,
                    chunk_id_to=None,
                    content_from=c_from.content,
                    content_to=None,
                )
            )

    for c_to in remaining_to:
        if c_to.chunk_id not in matched_to_ids:
            diffs.append(
                ChunkDiff(
                    change_type=ChangeType.ADDED,
                    chunk_id_from=None,
                    chunk_id_to=c_to.chunk_id,
                    content_from=None,
                    content_to=c_to.content,
                )
            )

    return diffs
