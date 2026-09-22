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
