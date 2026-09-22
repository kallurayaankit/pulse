"""pulse - continuous test-suite health monitor."""

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
from pulse.report import render_report

__version__ = "0.1.0"

__all__ = [
    "TestRun", "TestHistory", "TestAssessment",
    "TestStatus", "Recommendation",
    "ingest_directory", "build_histories",
    "detect_flaky", "detect_duplicates", "detect_low_value", "assess_all",
    "HealthMetrics", "compute_health", "compute_mttr",
    "compute_suite_flakiness", "compute_runtime_trend",
    "render_report",
]
