from app.modules.retrieval.fusion import reciprocal_rank_fusion, RRF_K


def test_rrf_boosts_chunk_present_in_both_lists():
    vector_ranked = [(1, "contenu A", {}), (2, "contenu B", {})]
    lexical_ranked = [(2, "contenu B", {}), (3, "contenu C", {})]

    fused = reciprocal_rank_fusion(vector_ranked, lexical_ranked)

    # chunk_id=2 est classé dans les deux listes -> score fusionné le plus élevé
    assert fused[0].chunk_id == 2
    expected_score_2 = 1.0 / (RRF_K + 2) + 1.0 / (RRF_K + 1)
    assert abs(fused[0].fused_score - expected_score_2) < 1e-9


def test_rrf_preserves_content_and_metadata():
    vector_ranked = [(1, "contenu unique", {"page": 3})]
    lexical_ranked = []

    fused = reciprocal_rank_fusion(vector_ranked, lexical_ranked)

    assert len(fused) == 1
    assert fused[0].content == "contenu unique"
    assert fused[0].metadata == {"page": 3}


def test_rrf_handles_empty_lists():
    assert reciprocal_rank_fusion([], []) == []


def test_rrf_sorted_descending_by_score():
    vector_ranked = [(1, "a", {}), (2, "b", {}), (3, "c", {})]
    lexical_ranked = []

    fused = reciprocal_rank_fusion(vector_ranked, lexical_ranked)

    scores = [c.fused_score for c in fused]
    assert scores == sorted(scores, reverse=True)
    assert [c.chunk_id for c in fused] == [1, 2, 3]  # ordre du rang vectoriel préservé
