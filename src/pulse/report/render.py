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

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out)
