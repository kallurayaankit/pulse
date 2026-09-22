"""Tests for flaky detection. No network."""

import pytest

from pulse.models import TestRun, TestHistory, TestStatus


def _run(run_id, status):
    return TestRun(test_id="t1", name="test_x", status=status, run_id=run_id)


def _history(statuses):
    h = TestHistory(test_id="t1", name="test_x")
    for i, s in enumerate(statuses):
        h.runs.append(_run("run-" + str(i).zfill(3), s))
    return h


def test_stable_pass_has_zero_flakiness():
    h = _history(["passed"] * 5)
    assert h.flakiness_score == 0.0


def test_stable_fail_has_zero_flakiness():
    """A test that always fails is a regression, not flaky."""
    h = _history(["failed"] * 5)
    assert h.flakiness_score == 0.0


def test_alternating_is_max_flaky():
    h = _history(["passed", "failed", "passed", "failed", "passed"])
    assert h.flakiness_score > 0.5


def test_transition_count():
    h = _history(["passed", "passed", "failed", "passed", "passed"])
    assert h.transition_count == 2


def test_single_run_is_not_flaky():
    h = _history(["passed"])
    assert h.flakiness_score == 0.0


def test_pass_rate():
    h = _history(["passed", "passed", "failed", "passed"])
    assert h.pass_rate == 0.75


def test_detect_flaky_finds_alternating():
    from pulse.analyze import detect_flaky
    h = _history(["passed", "failed", "passed", "failed", "passed"])
    assessments = detect_flaky([h])
    assert len(assessments) == 1
    assert assessments[0].is_flaky is True


def test_detect_flaky_skips_stable():
    from pulse.analyze import detect_flaky
    stable = _history(["passed"] * 5)
    assert detect_flaky([stable]) == []


def test_detect_flaky_skips_below_min_runs():
    from pulse.analyze import detect_flaky
    short = _history(["passed", "failed"])
    assert detect_flaky([short]) == []
