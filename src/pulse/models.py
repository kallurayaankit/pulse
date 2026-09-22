"""Core data model for pulse."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from time import time
from uuid import uuid4


def _short(prefix):
    return prefix + "-" + uuid4().hex[:6]


class TestStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class Recommendation(str, Enum):
    KEEP = "keep"
    QUARANTINE = "quarantine"
    REWRITE = "rewrite"
    PRUNE = "prune"
    INVESTIGATE = "investigate"


@dataclass
class TestRun:
    """One test execution result from one CI run."""
    test_id: str = ""
    name: str = ""
    file: str = ""
    status: str = TestStatus.PASSED.value
    duration_ms: float = 0.0
    run_id: str = ""
    commit_sha: str = ""
    timestamp: float = 0.0
    error_message: str = ""

    def to_dict(self):
        return asdict(self)

    @property
    def passed(self):
        return self.status == TestStatus.PASSED.value

    @property
    def failed(self):
        return self.status in (TestStatus.FAILED.value, TestStatus.ERROR.value)


@dataclass
class TestHistory:
    """All runs for one test."""
    test_id: str = ""
    name: str = ""
    file: str = ""
    runs: list = field(default_factory=list)

    @property
    def total_runs(self):
        return len(self.runs)

    @property
    def pass_count(self):
        return sum(1 for r in self.runs if r.passed)

    @property
    def fail_count(self):
        return sum(1 for r in self.runs if r.failed)

    @property
    def pass_rate(self):
        if not self.runs:
            return 0.0
        return self.pass_count / len(self.runs)

    @property
    def transition_count(self):
        """Number of pass<->fail flips on consecutive runs."""
        flips = 0
        for i in range(1, len(self.runs)):
            prev = self.runs[i - 1]
            curr = self.runs[i]
            if prev.passed != curr.passed:
                if prev.passed or curr.passed:
                    flips += 1
        return flips

    @property
    def flakiness_score(self):
        """0.0 = stable, 1.0 = maximally flaky.

        Based on transition frequency, not fail rate. A test that fails
        100% of the time is a regression, not flaky.
        """
        if self.total_runs < 2:
            return 0.0
        # A test that always passes or always fails has 0 flakiness
        if self.pass_count == 0 or self.fail_count == 0:
            return 0.0
        max_possible = self.total_runs - 1
        if max_possible == 0:
            return 0.0
        return min(1.0, self.transition_count / max_possible)

    @property
    def mean_duration_ms(self):
        if not self.runs:
            return 0.0
        return sum(r.duration_ms for r in self.runs) / len(self.runs)

    def to_dict(self):
        return {
            "test_id": self.test_id,
            "name": self.name,
            "file": self.file,
            "total_runs": self.total_runs,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "pass_rate": self.pass_rate,
            "transition_count": self.transition_count,
            "flakiness_score": self.flakiness_score,
            "mean_duration_ms": self.mean_duration_ms,
        }


@dataclass
class TestAssessment:
    """Pulse's verdict on one test."""
    test_id: str = ""
    name: str = ""
    file: str = ""
    is_flaky: bool = False
    is_duplicate: bool = False
    is_low_value: bool = False
    flakiness_score: float = 0.0
    value_score: float = 0.0
    duplicate_of: list = field(default_factory=list)
    recommendation: str = Recommendation.KEEP.value
    reason: str = ""

    def to_dict(self):
        return asdict(self)
