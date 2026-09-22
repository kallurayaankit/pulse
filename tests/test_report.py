"""Tests for the HTML report renderer. No network."""

from pathlib import Path

from pulse.ingest import ingest_directory, build_histories
from pulse.analyze import assess_all
from pulse.report import render_report


def _build():
    runs = ingest_directory("examples/reports")
    histories = build_histories(runs)
    assessments, health = assess_all(histories, runs)
    return assessments, health, histories


def test_render_creates_file(tmp_path):
    assessments, health, histories = _build()
    out = tmp_path / "report.html"
    path = render_report(assessments, health, histories, output_path=str(out))
    assert Path(path).exists()
    html = Path(path).read_text(encoding="utf-8")
    assert "pulse health report" in html
    assert "Health metrics" in html
    assert "Actionable findings" in html


def test_render_shows_flaky_count(tmp_path):
    assessments, health, histories = _build()
    out = tmp_path / "report.html"
    render_report(assessments, health, histories, output_path=str(out))
    html = Path(out).read_text(encoding="utf-8")
    assert "flaky" in html.lower()
    assert "MTTR" in html


def test_render_lists_all_tests(tmp_path):
    assessments, health, histories = _build()
    out = tmp_path / "report.html"
    render_report(assessments, health, histories, output_path=str(out))
    html = Path(out).read_text(encoding="utf-8")
    # Every test name should appear at least once
    for h in histories:
        assert h.name in html


def test_render_empty_state(tmp_path):
    """If there are no actionable findings, show the healthy message."""
    from pulse.metrics import HealthMetrics
    empty = HealthMetrics(total_tests=5, total_runs=10)
    out = tmp_path / "empty.html"
    render_report([], empty, [], output_path=str(out))
    html = Path(out).read_text(encoding="utf-8")
    assert "suite is healthy" in html.lower()
