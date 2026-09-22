"""Tests for duplicate detection."""

from pulse.analyze import detect_duplicates
from pulse.models import TestHistory, TestRun


def _hist(name, statuses, file="tests.test_auth"):
    h = TestHistory(test_id=file + "::" + name, name=name, file=file)
    for i, s in enumerate(statuses):
        h.runs.append(TestRun(
            test_id=h.test_id, name=name, file=file,
            status=s, run_id="run-" + str(i).zfill(3),
        ))
    return h


def test_identical_names_and_behavior_are_duplicates():
    a = _hist("test_login_valid", ["passed"] * 5)
    b = _hist("test_login_valid_user", ["passed"] * 5)
    results = detect_duplicates([a, b])
    assert len(results) >= 1
    assert any(r.is_duplicate for r in results)


def test_different_names_are_not_duplicates():
    a = _hist("test_login_valid", ["passed"] * 5)
    b = _hist("test_health_check", ["passed"] * 5)
    assert detect_duplicates([a, b]) == []


def test_different_files_are_not_duplicates():
    a = _hist("test_login_valid", ["passed"] * 5, file="tests.test_auth")
    b = _hist("test_login_valid", ["passed"] * 5, file="tests.test_other")
    assert detect_duplicates([a, b]) == []


def test_divergent_behavior_reduces_score():
    """Similar names but opposite pass/fail patterns shouldn't be flagged."""
    a = _hist("test_login_valid", ["passed"] * 5)
    b = _hist("test_login_valid_alt", ["failed"] * 5)
    results = detect_duplicates([a, b])
    # Behavior divergence should push score below threshold
    assert results == [] or all(
        len(r.duplicate_of) == 0 for r in results
    )
