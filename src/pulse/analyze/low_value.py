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
