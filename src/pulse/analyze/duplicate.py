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
