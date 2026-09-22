"""Tests for low-value detection."""

from pulse.analyze import detect_low_value
from pulse.models import TestHistory, TestRun


def _hist(name, statuses, file="tests.test_auth"):
    h = TestHistory(test_id=file + "::" + name, name=name, file=file)
    for i, s in enumerate(statuses):
        h.runs.append(TestRun(
            test_id=h.test_id, name=name, file=file,
            status=s, run_id="run-" + str(i).zfill(3),
        ))
    return h


def test_never_failed_test_is_low_value():
    a = _hist("test_login_alpha", ["passed"] * 5)
    b = _hist("test_login_beta", ["passed"] * 5)
    results = detect_low_value([a, b])
    assert len(results) >= 1


def test_ever_failed_test_has_value():
    h = _hist("test_login_critical", ["passed", "passed", "failed", "passed", "passed"])
    results = detect_low_value([h])
    assert results == []


def test_short_history_is_not_judged():
    h = _hist("test_xyz", ["passed"])
    assert detect_low_value([h]) == []
