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
