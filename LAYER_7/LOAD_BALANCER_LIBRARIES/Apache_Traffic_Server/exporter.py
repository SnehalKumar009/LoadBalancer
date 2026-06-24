"""Minimal ATS -> Prometheus metrics exporter.

Why this exists:
- ATS /_stats returns JSON whose keys contain literal dots (e.g.
  "proxy.process.http.completed_requests"). Off-the-shelf json_exporter
  fights us on path-escape syntax. A 30-line Python script is more reliable.

What it does:
- Listens on :9100. On every GET /metrics it fetches /_stats from ATS,
  walks the "global" object, and emits every numeric value as a Prometheus
  metric named  ats_<key_with_dots_turned_into_underscores>.
- No filtering / curated list — surfaces every metric ATS exposes.

Only depends on the Python stdlib (works in plain python:3.12-alpine).
"""

import http.server
import json
import re
import sys
import urllib.request

ATS_STATS_URL = "http://ats-lb:8081/_stats"
LISTEN_PORT = 9100
SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_]")


def fetch_and_render() -> bytes:
    """Pull /_stats from ATS and render Prometheus exposition text."""
    with urllib.request.urlopen(ATS_STATS_URL, timeout=4) as resp:
        payload = json.load(resp)

    lines = []
    for key, raw in payload.get("global", {}).items():
        # Only emit numeric values — strings like version/build date are skipped.
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        # proxy.process.http.completed_requests -> ats_proxy_process_http_completed_requests
        metric_name = "ats_" + SAFE_NAME_RE.sub("_", key)
        lines.append(f"{metric_name} {value}")
    lines.append("")  # trailing newline required by Prom exposition format
    return "\n".join(lines).encode("utf-8")


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (stdlib name)
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = fetch_and_render()
            status = 200
        except Exception as err:  # noqa: BLE001 — surface any failure via 500
            body = f"# scrape error: {err}\n".encode("utf-8")
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # silence default access log noise
        pass


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("", LISTEN_PORT), MetricsHandler)
    print(f"ats-exporter listening on :{LISTEN_PORT}/metrics", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
