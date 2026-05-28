"""
Web dashboard for review trace history using Python stdlib http.server.

Usage:
    python -m sentinel.monitor.dashboard [--port 8080] [--trace-dir ./traces]

Then open http://localhost:8080 in a browser.
"""

from __future__ import annotations

import argparse
import http.server
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

STYLES = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }
h1 { font-size: 24px; margin-bottom: 24px; color: #58a6ff; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
.card h3 { font-size: 12px; text-transform: uppercase; color: #8b949e; margin-bottom: 8px; }
.card .value { font-size: 32px; font-weight: 700; color: #f0f6fc; }
.card .sub { font-size: 12px; color: #8b949e; margin-top: 4px; }
.section { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; margin-bottom: 24px; }
.section h2 { font-size: 16px; color: #f0f6fc; margin-bottom: 16px; }
.bar-chart { display: flex; flex-direction: column; gap: 8px; }
.bar-row { display: flex; align-items: center; gap: 8px; }
.bar-label { width: 160px; font-size: 13px; color: #c9d1d9; flex-shrink: 0; }
.bar-track { flex: 1; height: 24px; background: #21262d; border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; background: linear-gradient(90deg, #58a6ff, #1f6feb); border-radius: 4px; transition: width 0.3s; }
.bar-value { width: 80px; font-size: 13px; color: #8b949e; text-align: right; flex-shrink: 0; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #21262d; font-size: 13px; }
th { color: #8b949e; font-weight: 600; text-transform: uppercase; font-size: 11px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.badge-green { background: #1b4721; color: #3fb950; }
.badge-yellow { background: #4d3800; color: #d29922; }
.badge-red { background: #4d1111; color: #f85149; }
.empty { color: #8b949e; text-align: center; padding: 48px; }
"""


def load_traces(trace_dir: str) -> list[dict]:
    traces = []
    p = Path(trace_dir)
    if not p.is_dir():
        return traces
    for f in sorted(p.glob("trace_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            data["_filename"] = f.name
            data["_filetime"] = datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            traces.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return traces


def load_feedbacks(trace_dir: str) -> list[dict]:
    feedbacks: list[dict] = []
    p = Path(trace_dir)
    if not p.is_dir():
        return feedbacks
    for f in sorted(p.glob("feedback_trace_*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            if isinstance(data, list):
                feedbacks.extend(data)
            else:
                feedbacks.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return feedbacks


def _summarize_trace(trace: dict) -> dict:
    review_duration = 0.0
    review_findings = 0
    agent_totals: dict[str, float] = {}
    agent_counts: dict[str, int] = {}

    for event in trace.get("events", []):
        dur = event.get("duration_ms", 0) or 0
        review_duration += dur
        name = event.get("agent", "unknown")
        agent_totals[name] = agent_totals.get(name, 0) + dur
        agent_counts[name] = agent_counts.get(name, 0) + 1
        meta = event.get("metadata", {}) or {}
        if event["event"] == "review.completed":
            review_findings = meta.get("findings", 0)

    return {
        "duration": review_duration,
        "findings": review_findings,
        "agent_totals": agent_totals,
        "agent_counts": agent_counts,
    }


def build_summary_stats(traces: list[dict]) -> dict:
    total_duration = 0.0
    agent_totals: dict[str, float] = {}
    findings_over_time: list[dict] = []
    traces_with_findings = 0

    for trace in traces:
        summary = _summarize_trace(trace)
        total_duration += summary["duration"]
        for name, dur in summary["agent_totals"].items():
            agent_totals[name] = agent_totals.get(name, 0) + dur
        if summary["findings"] > 0:
            traces_with_findings += 1
        findings_over_time.append(
            {
                "time": trace.get("_filetime", ""),
                "findings": summary["findings"],
                "duration_ms": round(summary["duration"], 1),
            }
        )

    return {
        "total_reviews": len(traces),
        "total_events": sum(len(t.get("events", [])) for t in traces),
        "total_duration_ms": round(total_duration, 1),
        "traces_with_findings": traces_with_findings,
        "agent_totals": agent_totals,
        "findings_over_time": findings_over_time[-50:],
        "recent_traces": [
            {
                "filename": t["_filename"],
                "time": t["_filetime"],
                "events": len(t.get("events", [])),
            }
            for t in traces[:20]
        ],
    }


def _summary_cards_html(stats: dict) -> str:
    cards = [
        ("Total Reviews", stats["total_reviews"], "trace files loaded"),
        ("Total Events", stats["total_events"], "trace events captured"),
        ("Total Duration", f"{stats['total_duration_ms']:.0f}ms", "aggregated across reviews"),
        ("Reviews w/ Findings", stats["traces_with_findings"], "traces containing issues"),
    ]
    parts = []
    for title, value, subtitle in cards:
        parts.append(
            f'<div class="card">'
            f"<h3>{title}</h3>"
            f'<div class="value">{value}</div>'
            f'<div class="sub">{subtitle}</div>'
            f"</div>"
        )
    return '<div class="grid">' + "\n  ".join(parts) + "\n</div>"


def _script_html(
    agents_json: str, timeline_json: str, recent_json: str, feedbacks_json: str
) -> str:
    return f"""<script>
const agents = {agents_json};
const timeline = {timeline_json};
const recent = {recent_json};
const feedbacks = {feedbacks_json};
const maxDur = Math.max(...agents.map(a => a.duration_ms), 1);
const chart = document.getElementById('agent-chart');

agents.forEach(a => {{
  const pct = (a.duration_ms / maxDur * 100).toFixed(1);
  chart.innerHTML += `<div class="bar-row">
    <div class="bar-label">${{a.name}}</div>
    <div class="bar-track"><div class="bar-fill" style="width:${{pct}}%"></div></div>
    <div class="bar-value">${{a.duration_ms}}ms</div>
  </div>`;
}});

const recentDiv = document.getElementById('recent-table');
if (recent.length === 0) {{
  recentDiv.innerHTML = '<div class="empty">No traces found. Run a review with --trace-dir first.</div>';
}} else {{
  let html = '<table><thead><tr><th>File</th><th>Time</th><th>Events</th></tr></thead><tbody>';
  recent.forEach(r => {{
    html += `<tr><td>${{r.filename}}</td><td>${{r.time}}</td><td>${{r.events}}</td></tr>`;
  }});
  html += '</tbody></table>';
  recentDiv.innerHTML = html;
}}

if (timeline.length > 0) {{
  const canvas = document.getElementById('trend-chart');
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.parentElement.clientWidth * 2;
  canvas.height = 400;
  const w = canvas.width, h = canvas.height;
  const pad = {{left: 60, right: 20, top: 20, bottom: 40}};
  const cw = w - pad.left - pad.right;
  const ch = h - pad.top - pad.bottom;
  const maxF = Math.max(...timeline.map(t => t.findings), 1);

  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = '#30363d';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {{
    const y = pad.top + (ch / 4) * i;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(w - pad.right, y);
    ctx.stroke();
    ctx.fillStyle = '#8b949e';
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxF - (maxF / 4) * i), pad.left - 8, y + 4);
  }}

  ctx.strokeStyle = '#58a6ff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  timeline.forEach((t, i) => {{
    const x = pad.left + (cw / Math.max(timeline.length - 1, 1)) * i;
    const y = pad.top + ch - (t.findings / maxF) * ch;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }});
  ctx.stroke();

  ctx.fillStyle = '#1f6feb';
  timeline.forEach((t, i) => {{
    const x = pad.left + (cw / Math.max(timeline.length - 1, 1)) * i;
    const y = pad.top + ch - (t.findings / maxF) * ch;
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  }});
}}

const fbDiv = document.getElementById('feedback-section');
if (feedbacks.length === 0) {{
  fbDiv.innerHTML = '<div class="empty">No feedback recorded. Submit feedback via CLI or POST /api/feedback.</div>';
}} else {{
  let html = '<table><thead><tr><th>Finding</th><th>Type</th><th>Rating</th><th>Comment</th><th>Time</th></tr></thead><tbody>';
  feedbacks.forEach(f => {{
    html += `<tr><td>${{f.finding_id}}</td><td>${{f.feedback_type}}</td><td><span class="badge ${{f.rating === 'correct' ? 'badge-green' : f.rating === 'incorrect' ? 'badge-red' : 'badge-yellow'}}">${{f.rating}}</span></td><td>${{f.comment || '-'}}</td><td>${{f.timestamp || ''}}</td></tr>`;
  }});
  html += '</tbody></table>';
  fbDiv.innerHTML = html;
}}
</script>"""


def build_html(stats: dict, feedbacks: list[dict] | None = None) -> str:
    agents_json = json.dumps(
        [{"name": k, "duration_ms": round(v, 1)} for k, v in stats["agent_totals"].items()]
    )
    timeline_json = json.dumps(stats["findings_over_time"])
    recent_json = json.dumps(stats["recent_traces"])
    feedbacks_json = json.dumps(feedbacks or [])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Code Review Dashboard</title>
<style>{STYLES}</style>
</head>
<body>
<h1>Code Review Dashboard</h1>
{_summary_cards_html(stats)}
<div class="section">
  <h2>Agent Duration Breakdown</h2>
  <div class="bar-chart" id="agent-chart"></div>
</div>
<div class="section">
  <h2>Trend (Last 50 Reviews)</h2>
  <canvas id="trend-chart" height="200" style="width:100%;"></canvas>
</div>
<div class="section">
  <h2>Recent Traces</h2>
  <div id="recent-table"></div>
</div>
<div class="section">
  <h2>Feedback</h2>
  <div id="feedback-section"></div>
</div>
{_script_html(agents_json, timeline_json, recent_json, feedbacks_json)}
</body>
</html>"""


@dataclass
class DashboardConfig:
    host: str = "localhost"
    port: int = 8080
    trace_dir: str = "./traces"
    open_browser: bool = False

    @classmethod
    def from_args(cls, argv: list[str] | None = None) -> DashboardConfig:
        parser = argparse.ArgumentParser(description="Code Review Dashboard")
        parser.add_argument("--port", "-p", type=int, default=8080, help="Port (default: 8080)")
        parser.add_argument(
            "--host", type=str, default="localhost", help="Host (default: localhost)"
        )
        parser.add_argument("--trace-dir", type=str, default="./traces", help="Trace directory")
        parser.add_argument("--open", action="store_true", help="Open browser automatically")
        args, _ = parser.parse_known_args(argv)
        return cls(host=args.host, port=args.port, trace_dir=args.trace_dir, open_browser=args.open)


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    config: DashboardConfig = DashboardConfig()

    def do_GET(self) -> None:
        if self.path == "/api/stats":
            traces = load_traces(self.config.trace_dir)
            stats = build_summary_stats(traces)
            self._send_json(stats)
            return

        if self.path == "/api/traces":
            traces = load_traces(self.config.trace_dir)
            self._send_json(traces)
            return

        if self.path == "/api/feedback":
            feedbacks = load_feedbacks(self.config.trace_dir)
            self._send_json(feedbacks)
            return

        stats = build_summary_stats(load_traces(self.config.trace_dir))
        feedbacks = load_feedbacks(self.config.trace_dir)
        html = build_html(stats, feedbacks)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_POST(self) -> None:
        if self.path != "/api/feedback":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._send_json({"status": "error", "message": "Empty body"})
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"status": "error", "message": "Invalid JSON"})
            return

        trace_file = data.get("trace_file", "")
        if not trace_file:
            self._send_json({"status": "error", "message": "trace_file is required"})
            return

        feedback_path = Path(self.config.trace_dir) / f"feedback_{trace_file}"
        existing: list[dict] = []
        if feedback_path.exists():
            try:
                existing = json.loads(feedback_path.read_text())
                if not isinstance(existing, list):
                    existing = [existing]
            except (json.JSONDecodeError, OSError):
                existing = []

        feedback_entry = {
            "finding_id": data.get("finding_id", ""),
            "trace_file": trace_file,
            "feedback_type": data.get("feedback_type", "human"),
            "rating": data.get("rating", "unsure"),
            "comment": data.get("comment", ""),
            "timestamp": datetime.now().isoformat(),
        }
        existing.append(feedback_entry)
        feedback_path.write_text(json.dumps(existing, indent=2))
        self._send_json({"status": "ok", "feedback": feedback_entry})

    def _send_json(self, data: dict | list) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format: str, *args: tuple) -> None:  # type: ignore[override]
        if args and args[0] == "GET":
            return
        super().log_message(format, *args)


def main(argv: list[str] | None = None) -> int:
    cfg = DashboardConfig.from_args(argv)

    DashboardHandler.config = cfg
    server = http.server.HTTPServer((cfg.host, cfg.port), DashboardHandler)
    url = f"http://{cfg.host}:{cfg.port}"
    print(f"Dashboard running at {url}", file=sys.stderr)
    print(f"   Traces from: {cfg.trace_dir}", file=sys.stderr)
    print("   Press Ctrl+C to stop", file=sys.stderr)

    if cfg.open_browser:
        import webbrowser

        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
