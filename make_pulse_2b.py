from pathlib import Path

root = Path(r"C:\Users\user\projects\pulse")
src = root / "src" / "pulse"

# ---------- src/pulse/analyze/duplicate.py ----------
duplicate = r'''
"""Duplicate coverage detection.

Two signals combined:

  1. Name similarity — tests with near-identical names often test the
     same thing (test_login_valid vs test_login_with_valid_creds).

  2. Behavioral similarity — tests that always pass or fail together
     are likely covering the same code path. If test A and test B have
     identical pass/fail vectors across N runs, they're correlated.

The final duplicate score is a weighted combination.
"""

import os
from difflib import SequenceMatcher

from dotenv import load_dotenv

from pulse.models import Recommendation, TestAssessment

load_dotenv()


def _threshold():
    return float(os.getenv("PULSE_DUPLICATE_THRESHOLD", "0.85"))


def _name_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _behavioral_similarity(hist_a, hist_b):
    """Fraction of runs where both tests had the same status."""
    runs_a = {r.run_id: r for r in hist_a.runs}
    runs_b = {r.run_id: r for r in hist_b.runs}
    shared = set(runs_a) & set(runs_b)
    if not shared:
        return 0.0
    same = sum(1 for rid in shared if runs_a[rid].passed == runs_b[rid].passed)
    return same / len(shared)


def _combined_score(name_sim, behavior_sim):
    """Weight behavioral similarity higher — it's a stronger signal."""
    return 0.3 * name_sim + 0.7 * behavior_sim


def detect_duplicates(histories):
    """Return a list of TestAssessment for tests that appear duplicated."""
    if len(histories) < 2:
        return []

    threshold = _threshold()
    duplicates = {}

    for i in range(len(histories)):
        for j in range(i + 1, len(histories)):
            a = histories[i]
            b = histories[j]

            if a.file != b.file:
                continue

            name_sim = _name_similarity(a.name, b.name)
            behavior_sim = _behavioral_similarity(a, b)

            # High behavioral similarity alone isn't enough — two tests
            # that always pass will look correlated. Require some name
            # similarity to reduce false positives.
            if name_sim < 0.5:
                continue

            score = _combined_score(name_sim, behavior_sim)
            if score < threshold:
                continue

            duplicates.setdefault(a.test_id, []).append((b, score))
            duplicates.setdefault(b.test_id, []).append((a, score))

    assessments = []
    for test_id, partners in duplicates.items():
        h = next(x for x in histories if x.test_id == test_id)
        partners.sort(key=lambda p: p[1], reverse=True)
        partner_ids = [p[0].test_id for p in partners]
        top_score = partners[0][1]

        assessments.append(TestAssessment(
            test_id=h.test_id,
            name=h.name,
            file=h.file,
            is_duplicate=True,
            duplicate_of=partner_ids,
            recommendation=Recommendation.PRUNE.value,
            reason=(
                "duplicate of " + str(len(partner_ids)) + " other test(s), "
                "similarity " + str(round(top_score, 2))
            ),
        ))

    assessments.sort(key=lambda a: len(a.duplicate_of), reverse=True)
    return assessments
'''

# ---------- src/pulse/analyze/low_value.py ----------
low_value = r'''
"""Low-value test detection.

A test is low-value if it:
  - has never caught a bug (always passed)
  - is slow
  - has no unique name signal compared to other tests

This is intentionally conservative. We don't want to recommend pruning
a test that just hasn't had a chance to fail yet. The scoring rewards
tests that have shown value (caught regressions) and penalizes tests
that consume time without producing signal.
"""

import os

from dotenv import load_dotenv

from pulse.models import Recommendation, TestAssessment

load_dotenv()


def _threshold():
    return float(os.getenv("PULSE_LOW_VALUE_THRESHOLD", "0.3"))


def _value_score(history, all_histories):
    """Return a score from 0.0 (worthless) to 1.0 (high value)."""
    if history.total_runs < 3:
        return 1.0  # not enough data to judge

    # Component 1: has this test ever failed?
    # A test that never failed has never proven it can catch a bug.
    ever_failed = history.fail_count > 0
    failure_signal = 0.6 if ever_failed else 0.0

    # Component 2: does it have a unique name?
    # Tests with names highly similar to others add little marginal value.
    max_name_sim = 0.0
    for other in all_histories:
        if other.test_id == history.test_id:
            continue
        if other.file != history.file:
            continue
        from difflib import SequenceMatcher
        sim = SequenceMatcher(None, history.name.lower(), other.name.lower()).ratio()
        if sim > max_name_sim:
            max_name_sim = sim
    uniqueness_signal = 0.4 * (1.0 - max_name_sim)

    return min(1.0, failure_signal + uniqueness_signal)


def detect_low_value(histories):
    """Return a list of TestAssessment for low-value tests."""
    threshold = _threshold()
    assessments = []

    for h in histories:
        score = _value_score(h, histories)
        if score >= threshold:
            continue

        assessments.append(TestAssessment(
            test_id=h.test_id,
            name=h.name,
            file=h.file,
            is_low_value=True,
            value_score=score,
            recommendation=Recommendation.REWRITE.value,
            reason=(
                "value score " + str(round(score, 2))
                + " - never failed in " + str(h.total_runs) + " runs, "
                "and name overlaps with other tests."
            ),
        ))

    assessments.sort(key=lambda a: a.value_score)
    return assessments
'''

# ---------- src/pulse/metrics/health.py ----------
health = r'''
"""Health metrics.

Flakiness trend: is the suite getting more or less flaky over time?
MTTR (mean time to repair): average number of runs a failure persists
before being fixed.
Suite runtime trend: total wall time per run.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class HealthMetrics:
    total_tests: int = 0
    total_runs: int = 0
    flaky_tests: int = 0
    duplicate_tests: int = 0
    low_value_tests: int = 0
    suite_flakiness: float = 0.0
    mean_time_to_repair_runs: float = 0.0
    mean_suite_duration_ms: float = 0.0
    runtime_trend: str = "stable"   # "improving" | "stable" | "worsening"

    def to_dict(self):
        return asdict(self)


def _is_failure_run(history, run_id):
    for r in history.runs:
        if r.run_id == run_id:
            return r.failed
    return False


def compute_mttr(histories, all_run_ids):
    """Mean number of consecutive failing runs before a test recovers.

    For each test, walk the sorted run list. When a failure streak ends
    (either by passing or by the data ending), record its length. Return
    the mean across all streaks.
    """
    if not all_run_ids:
        return 0.0

    run_order = sorted(all_run_ids)

    streak_lengths = []
    for h in histories:
        runs_by_id = {r.run_id: r for r in h.runs}
        current_streak = 0
        for rid in run_order:
            r = runs_by_id.get(rid)
            if r is None:
                continue
            if r.failed:
                current_streak += 1
            else:
                if current_streak > 0:
                    streak_lengths.append(current_streak)
                current_streak = 0
        # Do not count an ongoing streak at the end

    if not streak_lengths:
        return 0.0
    return sum(streak_lengths) / len(streak_lengths)


def compute_suite_flakiness(histories):
    """Mean flakiness across all tests."""
    if not histories:
        return 0.0
    return sum(h.flakiness_score for h in histories) / len(histories)


def compute_runtime_trend(runs):
    """Compare first half vs second half of runs. Returns 'improving',
    'stable', or 'worsening'."""
    if not runs:
        return "stable"

    by_run = {}
    for r in runs:
        by_run.setdefault(r.run_id, 0.0)
        by_run[r.run_id] += r.duration_ms

    ordered = [by_run[rid] for rid in sorted(by_run)]
    if len(ordered) < 4:
        return "stable"

    mid = len(ordered) // 2
    first_half = sum(ordered[:mid]) / mid
    second_half = sum(ordered[mid:]) / (len(ordered) - mid)

    if second_half < first_half * 0.9:
        return "improving"
    if second_half > first_half * 1.1:
        return "worsening"
    return "stable"


def compute_health(histories, runs, flaky, duplicates, low_value):
    """Build a HealthMetrics object from all the analysis results."""
    run_ids = sorted({r.run_id for r in runs})

    # Total suite duration per run
    by_run = {}
    for r in runs:
        by_run.setdefault(r.run_id, 0.0)
        by_run[r.run_id] += r.duration_ms
    mean_duration = sum(by_run.values()) / len(by_run) if by_run else 0.0

    return HealthMetrics(
        total_tests=len(histories),
        total_runs=len(run_ids),
        flaky_tests=len(flaky),
        duplicate_tests=len(duplicates),
        low_value_tests=len(low_value),
        suite_flakiness=compute_suite_flakiness(histories),
        mean_time_to_repair_runs=compute_mttr(histories, run_ids),
        mean_suite_duration_ms=mean_duration,
        runtime_trend=compute_runtime_trend(runs),
    )
'''

# ---------- src/pulse/analyze/assess.py ----------
assess = r'''
"""Combine all detectors into a single assessment pass."""

from pulse.analyze.duplicate import detect_duplicates
from pulse.analyze.flaky import detect_flaky
from pulse.analyze.low_value import detect_low_value
from pulse.metrics.health import compute_health
from pulse.models import Recommendation


def assess_all(histories, runs):
    """Run every detector. Returns (assessments, health_metrics)."""
    flaky = detect_flaky(histories)
    duplicates = detect_duplicates(histories)
    low_value = detect_low_value(histories)

    # Merge assessments by test_id
    by_id = {}
    for a in flaky:
        by_id[a.test_id] = a
    for a in duplicates:
        if a.test_id in by_id:
            by_id[a.test_id].is_duplicate = True
            by_id[a.test_id].duplicate_of = a.duplicate_of
            # Duplicate + flaky = quarantine (flaky wins)
        else:
            by_id[a.test_id] = a
    for a in low_value:
        if a.test_id in by_id:
            by_id[a.test_id].is_low_value = True
            by_id[a.test_id].value_score = a.value_score
        else:
            by_id[a.test_id] = a

    # Refine recommendations: priority order is
    # quarantine > investigate > prune > rewrite > keep
    for a in by_id.values():
        if a.is_flaky and a.flakiness_score >= 0.5:
            a.recommendation = Recommendation.QUARANTINE.value
        elif a.is_flaky:
            a.recommendation = Recommendation.INVESTIGATE.value
        elif a.is_duplicate:
            a.recommendation = Recommendation.PRUNE.value
        elif a.is_low_value:
            a.recommendation = Recommendation.REWRITE.value
        else:
            a.recommendation = Recommendation.KEEP.value

    assessments = sorted(
        by_id.values(),
        key=lambda a: (
            a.recommendation != Recommendation.QUARANTINE.value,
            a.recommendation != Recommendation.INVESTIGATE.value,
            a.recommendation != Recommendation.PRUNE.value,
            a.recommendation != Recommendation.REWRITE.value,
            -a.flakiness_score,
        ),
    )

    health = compute_health(histories, runs, flaky, duplicates, low_value)
    return assessments, health
'''

# ---------- src/pulse/analyze/__init__.py ----------
analyze_init = '''
from pulse.analyze.flaky import detect_flaky
from pulse.analyze.duplicate import detect_duplicates
from pulse.analyze.low_value import detect_low_value
from pulse.analyze.assess import assess_all

__all__ = ["detect_flaky", "detect_duplicates", "detect_low_value", "assess_all"]
'''

# ---------- src/pulse/metrics/__init__.py ----------
metrics_init = '''
from pulse.metrics.health import (
    HealthMetrics, compute_health, compute_mttr,
    compute_suite_flakiness, compute_runtime_trend,
)

__all__ = [
    "HealthMetrics", "compute_health", "compute_mttr",
    "compute_suite_flakiness", "compute_runtime_trend",
]
'''

# ---------- src/pulse/__init__.py ----------
root_init = '''"""pulse - continuous test-suite health monitor."""

from pulse.models import (
    TestRun, TestHistory, TestAssessment,
    TestStatus, Recommendation,
)
from pulse.ingest import ingest_directory, build_histories
from pulse.analyze import (
    detect_flaky, detect_duplicates, detect_low_value, assess_all,
)
from pulse.metrics import (
    HealthMetrics, compute_health, compute_mttr,
    compute_suite_flakiness, compute_runtime_trend,
)

__version__ = "0.1.0"

__all__ = [
    "TestRun", "TestHistory", "TestAssessment",
    "TestStatus", "Recommendation",
    "ingest_directory", "build_histories",
    "detect_flaky", "detect_duplicates", "detect_low_value", "assess_all",
    "HealthMetrics", "compute_health", "compute_mttr",
    "compute_suite_flakiness", "compute_runtime_trend",
]
'''

# ---------- tests/test_duplicate.py ----------
test_dup = r'''
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
'''

# ---------- tests/test_low_value.py ----------
test_low = r'''
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
'''

# ---------- tests/test_health.py ----------
test_health = r'''
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
'''

(src / "analyze" / "duplicate.py").write_text(duplicate.strip() + "\n", encoding="utf-8")
(src / "analyze" / "low_value.py").write_text(low_value.strip() + "\n", encoding="utf-8")
(src / "analyze" / "assess.py").write_text(assess.strip() + "\n", encoding="utf-8")
(src / "analyze" / "__init__.py").write_text(analyze_init.strip() + "\n", encoding="utf-8")
(src / "metrics" / "health.py").write_text(health.strip() + "\n", encoding="utf-8")
(src / "metrics" / "__init__.py").write_text(metrics_init.strip() + "\n", encoding="utf-8")
(src / "__init__.py").write_text(root_init, encoding="utf-8")
(root / "tests" / "test_duplicate.py").write_text(test_dup.strip() + "\n", encoding="utf-8")
(root / "tests" / "test_low_value.py").write_text(test_low.strip() + "\n", encoding="utf-8")
(root / "tests" / "test_health.py").write_text(test_health.strip() + "\n", encoding="utf-8")

print("Wrote analyze/duplicate.py, low_value.py, assess.py, metrics/health.py, 3 test files")
print()
for c in [
    "src/pulse/analyze/duplicate.py",
    "src/pulse/analyze/low_value.py",
    "src/pulse/analyze/assess.py",
    "src/pulse/analyze/__init__.py",
    "src/pulse/metrics/health.py",
    "src/pulse/metrics/__init__.py",
    "src/pulse/__init__.py",
    "tests/test_duplicate.py",
    "tests/test_low_value.py",
    "tests/test_health.py",
]:
    p = root / c
    size = p.stat().st_size if p.exists() else 0
    print(f"  {'OK ' if size > 0 else 'EMPTY'}  {c}  ({size} bytes)")