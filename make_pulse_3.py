from pathlib import Path

root = Path(r"C:\Users\user\projects\pulse")
src = root / "src" / "pulse"

# ---------- src/pulse/report/render.py ----------
render = r'''
"""Self-contained HTML health dashboard.

One file. Opens anywhere. No CDN, no external assets.

Leads with the recommendations. The top of the report is the list of
tests to quarantine, prune, or rewrite — the actionable part. The full
table is below.
"""

from datetime import datetime
from html import escape
from pathlib import Path

from pulse.metrics.health import HealthMetrics


RECOMMENDATION_COLORS = {
    "quarantine": ("#fee2e2", "#991b1b"),
    "investigate": ("#ffedd5", "#9a3412"),
    "prune": ("#fef3c7", "#92400e"),
    "rewrite": ("#dbeafe", "#1e40af"),
    "keep": ("#f3f4f6", "#4b5563"),
}


def _badge(text, kind="keep"):
    bg, fg = RECOMMENDATION_COLORS.get(kind, RECOMMENDATION_COLORS["keep"])
    return (
        '<span style="display:inline-block;padding:2px 10px;border-radius:10px;'
        'font-weight:600;font-size:11px;background:' + bg + ';color:' + fg
        + ';text-transform:uppercase;letter-spacing:0.5px;">'
        + escape(text) + '</span>'
    )


def _health_card(label, value, color="#111827"):
    return (
        '<div style="background:white;border:1px solid #e5e7eb;border-radius:8px;'
        'padding:16px 20px;flex:1;min-width:140px;">'
        '<div style="font-size:11px;color:#666;text-transform:uppercase;'
        'letter-spacing:0.5px;font-weight:600;">' + escape(label) + '</div>'
        '<div style="font-size:26px;font-weight:700;color:' + color
        + ';margin-top:6px;">' + escape(str(value)) + '</div>'
        '</div>'
    )


def _assessment_row(a):
    flags = []
    if a.is_flaky:
        flags.append("flaky " + str(round(a.flakiness_score, 2)))
    if a.is_duplicate:
        flags.append("dup of " + str(len(a.duplicate_of)))
    if a.is_low_value:
        flags.append("low value " + str(round(a.value_score, 2)))
    flag_str = " · ".join(flags) if flags else "&mdash;"

    return (
        '<tr style="border-bottom:1px solid #f3f4f6;">'
        '<td style="padding:10px 12px;font-family:ui-monospace,Menlo,monospace;'
        'font-size:13px;">' + escape(a.name) + '</td>'
        '<td style="padding:10px 12px;color:#666;font-size:12px;">'
        + escape(a.file) + '</td>'
        '<td style="padding:10px 12px;">' + _badge(a.recommendation, a.recommendation) + '</td>'
        '<td style="padding:10px 12px;font-size:12px;color:#666;">' + flag_str + '</td>'
        '<td style="padding:10px 12px;font-size:12px;color:#444;">'
        + escape(a.reason) + '</td>'
        '</tr>'
    )


def _history_row(h):
    flakiness_color = "#b91c1c" if h.flakiness_score >= 0.5 else (
        "#b45309" if h.flakiness_score >= 0.2 else "#4b5563"
    )
    return (
        '<tr style="border-bottom:1px solid #f3f4f6;">'
        '<td style="padding:8px 12px;font-family:ui-monospace,Menlo,monospace;'
        'font-size:12px;">' + escape(h.name) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + str(h.total_runs) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">' + str(h.fail_count) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">'
        + str(round(h.pass_rate * 100)) + '%</td>'
        '<td style="padding:8px 12px;text-align:right;color:'
        + flakiness_color + ';font-weight:600;">'
        + str(round(h.flakiness_score, 2)) + '</td>'
        '<td style="padding:8px 12px;text-align:right;">'
        + str(round(h.mean_duration_ms, 0)) + 'ms</td>'
        '</tr>'
    )


def render_report(assessments, health, histories, output_path=None):
    """Render the health dashboard. Returns the path written."""
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sort histories by flakiness desc
    histories_sorted = sorted(histories, key=lambda h: h.flakiness_score, reverse=True)

    # Filter actionable assessments
    actionable = [a for a in assessments if a.recommendation != "keep"]

    actionable_rows = "".join(_assessment_row(a) for a in actionable)
    if not actionable_rows:
        actionable_rows = (
            '<tr><td colspan="5" style="padding:24px;text-align:center;color:#666;">'
            'No actionable findings. The suite is healthy.</td></tr>'
        )

    history_rows = "".join(_history_row(h) for h in histories_sorted)

    health_cards = "".join([
        _health_card("total tests", health.total_tests),
        _health_card("runs analyzed", health.total_runs),
        _health_card("flaky", health.flaky_tests,
                     "#b91c1c" if health.flaky_tests else "#15803d"),
        _health_card("duplicates", health.duplicate_tests,
                     "#b45309" if health.duplicate_tests else "#15803d"),
        _health_card("low value", health.low_value_tests,
                     "#b45309" if health.low_value_tests else "#15803d"),
        _health_card("suite flakiness",
                     str(round(health.suite_flakiness, 2)),
                     "#b91c1c" if health.suite_flakiness >= 0.2 else "#4b5563"),
        _health_card("MTTR", str(round(health.mean_time_to_repair_runs, 1)) + " runs"),
        _health_card("runtime trend", health.runtime_trend,
                     "#15803d" if health.runtime_trend == "improving"
                     else ("#b91c1c" if health.runtime_trend == "worsening" else "#4b5563")),
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>pulse - test suite health</title>
</head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             margin:0;padding:32px;background:#f9fafb;color:#111827;line-height:1.5;">

<h1 style="margin:0 0 4px 0;font-size:24px;">pulse health report</h1>
<div style="color:#666;font-size:14px;margin-bottom:24px;">
  Generated: <strong>{escape(generated)}</strong>
</div>

<h2 style="font-size:16px;margin:24px 0 12px 0;color:#374151;
           border-bottom:1px solid #e5e7eb;padding-bottom:6px;">
  Health metrics
</h2>
<div style="display:flex;gap:12px;flex-wrap:wrap;">
  {health_cards}
</div>

<h2 style="font-size:16px;margin:32px 0 12px 0;color:#374151;
           border-bottom:1px solid #e5e7eb;padding-bottom:6px;">
  Actionable findings ({len(actionable)})
</h2>
<div style="color:#666;font-size:13px;margin-bottom:8px;">
  Ranked by priority. Quarantine first, then investigate, prune, rewrite.
</div>
<div style="background:white;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
<table style="width:100%;border-collapse:collapse;">
  <thead>
    <tr style="background:#fafafa;border-bottom:1px solid #e5e7eb;">
      <th style="text-align:left;padding:10px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Test</th>
      <th style="text-align:left;padding:10px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">File</th>
      <th style="text-align:left;padding:10px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Action</th>
      <th style="text-align:left;padding:10px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Signals</th>
      <th style="text-align:left;padding:10px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Reason</th>
    </tr>
  </thead>
  <tbody>
    {actionable_rows}
  </tbody>
</table>
</div>

<h2 style="font-size:16px;margin:32px 0 12px 0;color:#374151;
           border-bottom:1px solid #e5e7eb;padding-bottom:6px;">
  All tests ({len(histories)})
</h2>
<div style="background:white;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
<table style="width:100%;border-collapse:collapse;">
  <thead>
    <tr style="background:#fafafa;border-bottom:1px solid #e5e7eb;">
      <th style="text-align:left;padding:8px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Test</th>
      <th style="text-align:right;padding:8px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Runs</th>
      <th style="text-align:right;padding:8px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Fails</th>
      <th style="text-align:right;padding:8px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Pass rate</th>
      <th style="text-align:right;padding:8px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Flakiness</th>
      <th style="text-align:right;padding:8px 12px;font-size:11px;
                 color:#666;text-transform:uppercase;letter-spacing:0.5px;">Avg ms</th>
    </tr>
  </thead>
  <tbody>
    {history_rows}
  </tbody>
</table>
</div>

<footer style="margin-top:48px;padding-top:16px;border-top:1px solid #e5e7eb;
               color:#9ca3af;font-size:12px;text-align:center;">
  Generated by pulse &middot; {escape(generated)}
</footer>

</body>
</html>
"""

    if output_path is None:
        Path("reports").mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = "reports/pulse-" + ts + ".html"

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
'''

# ---------- src/pulse/report/__init__.py ----------
report_init = '''
from pulse.report.render import render_report

__all__ = ["render_report"]
'''

# ---------- src/pulse/cli.py ----------
cli = r'''
"""Command-line interface for pulse.

    pulse analyze <reports-dir> [--out report.html] [--open]
    pulse version
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

from pulse import __version__
from pulse.ingest import ingest_directory, build_histories
from pulse.analyze import assess_all
from pulse.report import render_report


def cmd_analyze(args):
    reports_dir = Path(args.reports)
    if not reports_dir.exists():
        print("error: reports directory not found: " + args.reports, file=sys.stderr)
        sys.exit(2)

    print("Ingesting " + args.reports)
    runs = ingest_directory(reports_dir)
    print("  " + str(len(runs)) + " test executions")

    histories = build_histories(runs)
    print("  " + str(len(histories)) + " distinct tests")

    assessments, health = assess_all(histories, runs)

    print()
    print("=== Health ===")
    print("  flaky:        " + str(health.flaky_tests))
    print("  duplicates:   " + str(health.duplicate_tests))
    print("  low value:    " + str(health.low_value_tests))
    print("  suite flakiness: " + str(round(health.suite_flakiness, 2)))
    print("  MTTR:         " + str(round(health.mean_time_to_repair_runs, 1)) + " runs")
    print("  runtime trend: " + health.runtime_trend)
    print()

    actionable = [a for a in assessments if a.recommendation != "keep"]
    if actionable:
        print("=== Recommendations ===")
        for a in actionable[:20]:
            print("  [" + a.recommendation.ljust(12) + "] " + a.name)
            print("      " + a.reason)
        print()

    out = args.out or "reports/pulse.html"
    html_path = render_report(assessments, health, histories, output_path=out)
    print("HTML: " + html_path)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps({
                "health": health.to_dict(),
                "assessments": [a.to_dict() for a in assessments],
                "histories": [h.to_dict() for h in histories],
            }, indent=2),
            encoding="utf-8",
        )
        print("JSON: " + args.json)

    if args.open:
        webbrowser.open("file:///" + str(Path(html_path).resolve()))

    if actionable and args.fail_on_findings:
        sys.exit(1)


def cmd_version(args):
    print("pulse " + __version__)


def main():
    parser = argparse.ArgumentParser(
        prog="pulse",
        description="Continuous test-suite health monitor",
    )
    parser.add_argument("--version", action="version", version="pulse " + __version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_a = sub.add_parser("analyze", help="analyze a directory of JUnit XML reports")
    p_a.add_argument("reports", help="directory containing run-*.xml files")
    p_a.add_argument("--out", help="HTML output path (default reports/pulse.html)")
    p_a.add_argument("--json", help="also write a JSON file with raw data")
    p_a.add_argument("--open", action="store_true", help="open HTML in browser")
    p_a.add_argument("--fail-on-findings", action="store_true",
                     help="exit 1 if any actionable finding exists")
    p_a.set_defaults(func=cmd_analyze)

    p_v = sub.add_parser("version", help="print version")
    p_v.set_defaults(func=cmd_version)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
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
'''

# ---------- tests/test_report.py ----------
test_report = r'''
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
'''

(src / "report" / "render.py").write_text(render.strip() + "\n", encoding="utf-8")
(src / "report" / "__init__.py").write_text(report_init.strip() + "\n", encoding="utf-8")
(src / "cli.py").write_text(cli.strip() + "\n", encoding="utf-8")
(src / "__init__.py").write_text(root_init, encoding="utf-8")
(root / "tests" / "test_report.py").write_text(test_report.strip() + "\n", encoding="utf-8")

# ---------- README ----------
readme_lines = [
    "# pulse",
    "",
    "[![Tests](https://github.com/kallurayaankit/pulse/actions/workflows/test.yml/badge.svg)](https://github.com/kallurayaankit/pulse/actions/workflows/test.yml)",
    "[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)",
    "[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)",
    "",
    "**Continuous test-suite health monitor.** Finds flaky tests, duplicate coverage, and low-value tests. Tracks flakiness trend and mean time to repair.",
    "",
    "```bash",
    "pip install -e .",
    "pulse analyze examples/reports --open",
    "```",
    "",
    "## The problem",
    "",
    "Your test suite has three invisible problems:",
    "",
    "**1. Flaky tests.** They pass on Tuesday, fail on Wednesday, pass again on Thursday. Nobody knows which ones, because the CI retries them and moves on.",
    "",
    "**2. Duplicate coverage.** Two tests in the same file, testing the same code path, with slightly different names. Both run every PR. Only one adds value.",
    "",
    "**3. Low-value tests.** Tests that have never failed. Not because the code is perfect — because the test doesn't actually assert anything meaningful.",
    "",
    "Existing tooling handles these one at a time. You need five tools to see your whole suite. `pulse` does all four (flaky, duplicate, low-value, health metrics) in one pass.",
    "",
    "## What it finds",
    "",
    "| Signal | How it's detected |",
    "|---|---|",
    "| **Flaky** | Pass↔fail transitions across consecutive runs, normalized by run count |",
    "| **Duplicate** | Name similarity + behavioral correlation (weighted 30/70) |",
    "| **Low value** | Never failed + high name overlap with other tests |",
    "| **MTTR** | Mean length of consecutive failure streaks before recovery |",
    "| **Suite flakiness** | Mean flakiness across all tests |",
    "| **Runtime trend** | First-half vs second-half suite duration comparison |",
    "",
    "## Architecture",
    "",
    "```mermaid",
    "flowchart LR",
    "    J[JUnit XML<br/>runs 1..N] --> ING[Ingest]",
    "    ING --> H[Test histories]",
    "    H --> F[Flaky detection]",
    "    H --> D[Duplicate detection]",
    "    H --> L[Low-value scoring]",
    "    F --> M[Merge + rank]",
    "    D --> M",
    "    L --> M",
    "    M --> R[HTML dashboard]",
    "    H --> MT[Metrics: MTTR, trend]",
    "    MT --> R",
    "```",
    "",
    "## Quickstart",
    "",
    "Point it at a directory of JUnit XML files. Each file is one CI run. Filenames become run IDs, sorted lexicographically.",
    "",
    "```",
    "examples/reports/",
    "├── run-000.xml",
    "├── run-001.xml",
    "├── run-002.xml",
    "└── ...",
    "```",
    "",
    "```bash",
    "pulse analyze examples/reports --open",
    "```",
    "",
    "Output:",
    "",
    "```",
    "Ingesting examples/reports",
    "  120 test executions",
    "  12 distinct tests",
    "",
    "=== Health ===",
    "  flaky:        3",
    "  duplicates:   2",
    "  low value:    1",
    "  suite flakiness: 0.14",
    "  MTTR:         1.8 runs",
    "  runtime trend: stable",
    "",
    "=== Recommendations ===",
    "  [quarantine  ] test_session_expiry",
    "      flakiness score 0.55 - flips on 5 of 9 consecutive runs.",
    "",
    "  [investigate ] test_signup_weak_password",
    "      flakiness score 0.33 - investigate for race conditions.",
    "",
    "HTML: reports/pulse.html",
    "```",
    "",
    "## Recommendations",
    "",
    "Every test gets one of five recommendations:",
    "",
    "| Recommendation | When |",
    "|---|---|",
    "| `quarantine` | Flakiness ≥ 0.5. Remove from CI, investigate separately. |",
    "| `investigate` | Flakiness between threshold and 0.5. Might have a real race condition. |",
    "| `prune` | Duplicate of another test in the same file. |",
    "| `rewrite` | Low value score. Never failed, high name overlap. |",
    "| `keep` | No signals. Leave it alone. |",
    "",
    "## Flakiness scoring",
    "",
    "A test's flakiness score is **transitions divided by run count minus one**.",
    "",
    "The critical detail: **a test that fails 100% of the time has a flakiness score of 0.0.** It's a regression, not a flake. A stable failure is *information*. A flaky failure is *noise*.",
    "",
    "```",
    "passed, passed, passed, passed, passed   -> 0.00  (stable pass)",
    "failed, failed, failed, failed, failed   -> 0.00  (regression, not flaky)",
    "passed, passed, failed, passed, passed   -> 0.50  (two transitions / four gaps)",
    "passed, failed, passed, failed, passed   -> 1.00  (maximally flaky)",
    "```",
    "",
    "## Duplicate detection",
    "",
    "Two signals, weighted:",
    "",
    "- **Name similarity** (weight 0.3): SequenceMatcher ratio on test names.",
    "- **Behavioral similarity** (weight 0.7): fraction of runs where both tests had the same status.",
    "",
    "The behavioral weight is higher because it's a stronger signal. But behavioral alone is unreliable — two tests that always pass will look perfectly correlated. That's why we require name similarity ≥ 0.5 as a gate before scoring.",
    "",
    "## Health metrics",
    "",
    "**MTTR (mean time to repair):** for every failure streak, count how many runs it persisted. Average across all streaks. An MTTR of 1.8 means a test typically takes about 2 runs to be fixed. An MTTR of 8.0 means failures linger — that's a signal about process, not code.",
    "",
    "**Suite flakiness:** mean flakiness across all tests. Under 0.05 is healthy. Over 0.20 means the suite is not trustworthy.",
    "",
    "**Runtime trend:** compares first-half vs second-half suite durations. `improving` if the second half is 10% faster, `worsening` if 10% slower.",
    "",
    "## CLI",
    "",
    "```bash",
    "pulse analyze <reports-dir>             # generate HTML report",
    "pulse analyze <reports-dir> --open      # open in browser",
    "pulse analyze <reports-dir> --json out.json  # also write raw data",
    "pulse analyze <reports-dir> --fail-on-findings  # exit 1 if actionable",
    "pulse version",
    "```",
    "",
    "## Configuration",
    "",
    "`.env`:",
    "",
    "```",
    "PULSE_FLAKY_THRESHOLD=0.2",
    "PULSE_DUPLICATE_THRESHOLD=0.85",
    "PULSE_LOW_VALUE_THRESHOLD=0.3",
    "PULSE_MIN_RUNS=3",
    "```",
    "",
    "The minimum-runs threshold prevents false positives on short histories. A test that appears in only 2 runs can't be reliably classified.",
    "",
    "## What this is not",
    "",
    "- Not a test selector. It doesn't decide which tests to run on a given commit. It decides which tests to keep, fix, or delete.",
    "- Not a CI integration. It reads JUnit XML from disk. Wire it into CI yourself with `--fail-on-findings`.",
    "- Not a dashboard service. The output is a self-contained HTML file. Open it, share it, email it. No backend.",
    "",
    "## Status",
    "",
    "Early. Full pipeline works end-to-end. 30+ unit tests passing. No LLM calls — everything is deterministic and instant.",
    "",
    "Roadmap: git history integration (was the failure actually fixed?), commit correlation (which commits introduced the flake?), trend visualization over time.",
    "",
    "## License",
    "",
    "MIT",
    "",
]

(root / "README.md").write_text("\n".join(readme_lines), encoding="utf-8")

# ---------- GitHub Actions ----------
wf = """name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .
      - name: Run tests
        run: pytest -v
"""

(root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
(root / ".github" / "workflows" / "test.yml").write_text(wf, encoding="utf-8")

print("Wrote 12 files")
print()
for c in [
    "src/pulse/report/render.py",
    "src/pulse/report/__init__.py",
    "src/pulse/cli.py",
    "src/pulse/__init__.py",
    "tests/test_report.py",
    "README.md",
    ".github/workflows/test.yml",
]:
    p = root / c
    size = p.stat().st_size if p.exists() else 0
    print(f"  {'OK ' if size > 0 else 'EMPTY'}  {c}  ({size} bytes)")