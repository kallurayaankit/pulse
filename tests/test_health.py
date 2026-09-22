"""Tests for health metrics."""

from pulse.metrics import (
    compute_mttr, compute_suite_flakiness, compute_runtime_trend,
)
from pulse.models import TestHistory, TestRun


def _history(test_id, statuses):
    h = TestHistory(test_id=test_id, name=test_id)
    for i, s in enumerate(statuses):
        h.runs.append(TestRun(
            test_id=test_id, name=test_id, status=s,
            run_id="run-" + str(i).zfill(3),
            duration_ms=100.0,
        ))
    return h


def test_mttr_single_streak():
    h = _history("t1", ["passed", "failed", "failed", "passed", "passed"])
    mttr = compute_mttr([h], ["run-000", "run-001", "run-002", "run-003", "run-004"])
    assert mttr == 2.0


def test_mttr_two_streaks_averaged():
    h = _history("t1", [
        "failed", "passed", "failed", "failed", "passed"
    ])
    mttr = compute_mttr([h], ["run-000", "run-001", "run-002", "run-003", "run-004"])
    assert mttr == 1.5  # streaks of 1 and 2


def test_mttr_no_failures():
    h = _history("t1", ["passed", "passed", "passed"])
    mttr = compute_mttr([h], ["run-000", "run-001", "run-002"])
    assert mttr == 0.0


def test_suite_flakiness_averages():
    a = _history("t1", ["passed", "failed", "passed", "failed"])
    b = _history("t2", ["passed", "passed", "passed", "passed"])
    flakiness = compute_suite_flakiness([a, b])
    assert 0.0 < flakiness < 1.0


def test_runtime_trend_improving():
    runs = []
    for i in range(8):
        # Second half faster than first
        d = 200.0 if i < 4 else 100.0
        runs.append(TestRun(run_id="run-" + str(i).zfill(3), duration_ms=d))
    assert compute_runtime_trend(runs) == "improving"


def test_runtime_trend_worsening():
    runs = []
    for i in range(8):
        d = 100.0 if i < 4 else 200.0
        runs.append(TestRun(run_id="run-" + str(i).zfill(3), duration_ms=d))
    assert compute_runtime_trend(runs) == "worsening"


def test_runtime_trend_stable():
    runs = []
    for i in range(8):
        runs.append(TestRun(run_id="run-" + str(i).zfill(3), duration_ms=150.0))
    assert compute_runtime_trend(runs) == "stable"
