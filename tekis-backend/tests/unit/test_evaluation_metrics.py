from app.modules.evaluation import metrics


def test_precision_at_k_all_relevant():
    assert metrics.precision_at_k([1, 2, 3], {1, 2, 3}, k=3) == 1.0


def test_precision_at_k_partial():
    assert metrics.precision_at_k([1, 2, 3], {1}, k=3) == 1 / 3


def test_precision_at_k_zero_k_returns_zero():
    assert metrics.precision_at_k([1, 2], {1}, k=0) == 0.0


def test_precision_at_k_empty_retrieved_returns_zero():
    assert metrics.precision_at_k([], {1}, k=3) == 0.0


def test_recall_at_k_finds_all_relevant():
    assert metrics.recall_at_k([1, 2, 3], {1, 2}, k=3) == 1.0


def test_recall_at_k_misses_some():
    assert metrics.recall_at_k([1], {1, 2}, k=1) == 0.5


def test_recall_at_k_no_relevant_expected_returns_zero():
    assert metrics.recall_at_k([1, 2], set(), k=2) == 0.0


def test_reciprocal_rank_first_position():
    assert metrics.reciprocal_rank([1, 2, 3], {1}) == 1.0


def test_reciprocal_rank_third_position():
    assert metrics.reciprocal_rank([9, 8, 1], {1}) == 1 / 3


def test_reciprocal_rank_not_found_returns_zero():
    assert metrics.reciprocal_rank([9, 8, 7], {1}) == 0.0


def test_keyword_coverage_full_match():
    assert metrics.keyword_coverage("La panne réseau dure vingt minutes.", ["panne", "vingt"]) == 1.0


def test_keyword_coverage_partial_match_case_insensitive():
    assert metrics.keyword_coverage("La PANNE dure longtemps.", ["panne", "vingt"]) == 0.5


def test_keyword_coverage_no_expected_keywords_returns_one():
    assert metrics.keyword_coverage("Peu importe la réponse.", []) == 1.0


def test_keyword_coverage_none_answer_returns_zero():
    assert metrics.keyword_coverage(None, ["panne"]) == 0.0


def test_abstention_correctness_true_positive():
    assert metrics.abstention_correctness(expected_abstain=True, actual_abstained=True) is True


def test_abstention_correctness_false_when_mismatched():
    assert metrics.abstention_correctness(expected_abstain=True, actual_abstained=False) is False


def test_acl_leak_count_detects_forbidden_source():
    assert metrics.acl_leak_count([1, 2, 3], {2}) == 1


def test_acl_leak_count_zero_when_no_forbidden_ids_defined():
    assert metrics.acl_leak_count([1, 2, 3], set()) == 0


def test_acl_leak_count_zero_when_no_leak():
    assert metrics.acl_leak_count([1, 3], {2}) == 0


def test_ndcg_at_k_perfect_ranking():
    assert metrics.ndcg_at_k([1, 2], {1: 3, 2: 2}, 2) == 1.0

def test_ndcg_at_k_penalizes_bad_order():
    assert metrics.ndcg_at_k([2, 1], {1: 3, 2: 2}, 2) < 1.0
