"""Self-contained HTML backtest report.

Renders the metrics table and an inline SVG equity curve into a single HTML
string — no JS, no chart library, no external assets — so a result is easy to
save and share.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from datetime import datetime

from .metrics import Metrics


def _equity_svg(
    equity_curve: Sequence[tuple[datetime, float]], width: int = 720, height: int = 240
) -> str:
    values = [v for _, v in equity_curve]
    if len(values) < 2:
        return '<p class="muted">No equity data.</p>'
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(values)
    points = " ".join(
        f"{i / (n - 1) * width:.1f},{height - (v - lo) / span * height:.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        'preserveAspectRatio="none" role="img" aria-label="Equity curve">'
        f'<polyline points="{points}" fill="none" stroke="#3b82f6" stroke-width="2"/>'
        "</svg>"
    )


def _metrics_table(metrics: Metrics) -> str:
    rows = []
    for line in metrics.as_table().splitlines():
        label, _, value = line.partition(" : ")
        rows.append(
            f"<tr><td>{html.escape(label.strip())}</td><td>{html.escape(value.strip())}</td></tr>"
        )
    return "<table>" + "".join(rows) + "</table>"


def render_html(
    metrics: Metrics,
    equity_curve: Sequence[tuple[datetime, float]],
    title: str = "Backtest report",
) -> str:
    """Render a complete, self-contained HTML report."""
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{safe_title}</title>
<style>
  body {{
    font-family: system-ui, sans-serif;
    background:#0b0e14; color:#e6edf3; margin:0; padding:24px;
  }}
  h1 {{ font-size:18px; }}
  .muted {{ color:#8a97a8; }}
  .panel {{
    background:#141a24; border:1px solid #222b39;
    border-radius:8px; padding:16px; margin-bottom:16px;
  }}
  table {{ border-collapse:collapse; width:100%; max-width:420px; }}
  td {{ padding:4px 8px; border-top:1px solid #222b39; }}
  td:first-child {{ color:#8a97a8; }}
</style>
</head>
<body>
  <h1>{safe_title}</h1>
  <div class="panel">{_equity_svg(equity_curve)}</div>
  <div class="panel">{_metrics_table(metrics)}</div>
</body>
</html>
"""
