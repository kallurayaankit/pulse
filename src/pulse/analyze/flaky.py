"""Flaky test detection.

A test is flaky if it flips between pass and fail on the same commit
without code changing. We measure this as the transition frequency
across consecutive runs.

The key insight: a test that fails 100% of the time is a regression,
not flaky. A test that passes 60% and fails 40% with high transition
frequency IS flaky.
"""

import os

from dotenv import load_dotenv

from pulse.models import Recommendation, TestAssessment

load_dotenv()


def _threshold():
    return float(os.getenv("PULSE_FLAKY_THRESHOLD", "0.2"))


def _min_runs():
    return int(os.getenv("PULSE_MIN_RUNS", "3"))


def detect_flaky(histories):
    """Return a list of TestAssessment for flaky tests."""
    threshold = _threshold()
    min_runs = _min_runs()

    assessments = []
    for h in histories:
        if h.total_runs < min_runs:
            continue
        if h.flakiness_score < threshold:
            continue

        # Determine recommendation
        if h.flakiness_score >= 0.5:
            rec = Recommendation.QUARANTINE.value
            reason = (
                "flakiness score " + str(round(h.flakiness_score, 2))
                + " - flips on " + str(h.transition_count) + " of "
                + str(h.total_runs - 1) + " consecutive runs. "
                "Quarantine and investigate."
            )
        else:
            rec = Recommendation.INVESTIGATE.value
            reason = (
                "flakiness score " + str(round(h.flakiness_score, 2))
                + " - investigate for race conditions or timing dependencies."
            )

        assessments.append(TestAssessment(
            test_id=h.test_id,
            name=h.name,
            file=h.file,
            is_flaky=True,
            flakiness_score=h.flakiness_score,
            recommendation=rec,
            reason=reason,
        ))

    assessments.sort(key=lambda a: a.flakiness_score, reverse=True)
    return assessments
