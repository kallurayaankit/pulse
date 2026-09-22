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
