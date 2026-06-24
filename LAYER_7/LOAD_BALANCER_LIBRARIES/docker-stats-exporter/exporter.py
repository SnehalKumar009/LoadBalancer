#!/usr/bin/env python3
"""
Tiny Docker stats -> Prometheus exporter.

Why a custom exporter instead of cAdvisor:
  cAdvisor (as of v0.52.1) hard-fails container registration when Docker
  uses the containerd image snapshotter (the new default on recent
  kernels). It tries to read /var/lib/docker/image/<driver>/layerdb/...
  which no longer exists in that layout, so every container ends up
  without a `name` label and Grafana panels show "No Data".

  This script talks directly to the Docker socket and emits the same
  metric names the dashboard already queries:
      container_cpu_usage_seconds_total{name="<container>"}
      container_memory_working_set_bytes{name="<container>"}

Exposes /metrics on :9100 in Prometheus exposition format.
"""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DOCKER_SOCK = "/var/run/docker.sock"


class UnixHTTPConnection(HTTPConnection):
    """HTTPConnection that talks to a Unix domain socket instead of TCP."""

    def __init__(self, path):
        super().__init__("localhost")
        self._unix_path = path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self._unix_path)
        self.sock = s


def docker_get(path):
    c = UnixHTTPConnection(DOCKER_SOCK)
    try:
        c.request("GET", path)
        r = c.getresponse()
        return json.loads(r.read())
    finally:
        c.close()


def fetch_stats(cid):
    return docker_get(f"/containers/{cid}/stats?stream=false")


def collect():
    containers = docker_get("/containers/json")

    lines = [
        "# HELP container_cpu_usage_seconds_total Cumulative CPU time consumed (seconds).",
        "# TYPE container_cpu_usage_seconds_total counter",
        "# HELP container_memory_working_set_bytes Current working set (bytes).",
        "# TYPE container_memory_working_set_bytes gauge",
    ]

    # Fetch every container's stats in parallel; the docker stats endpoint
    # blocks for ~1s per call so serial scraping would be slow.
    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(lambda c: (c, fetch_stats(c["Id"])), containers))

    for c, s in results:
        name = c["Names"][0].lstrip("/")
        image = c.get("Image", "")

        # CPU: total_usage is cumulative nanoseconds since container start.
        cpu_ns = s.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
        cpu_seconds = cpu_ns / 1e9

        # Memory working set = usage - inactive_file (matches cAdvisor's
        # definition). Field name differs between cgroup v1 and v2.
        mem = s.get("memory_stats") or {}
        usage = mem.get("usage", 0) or 0
        stats = mem.get("stats") or {}
        inactive = stats.get("inactive_file") or stats.get("total_inactive_file") or 0
        working_set = max(usage - inactive, 0)

        labels = f'name="{name}",image="{image}"'
        lines.append(f"container_cpu_usage_seconds_total{{{labels}}} {cpu_seconds}")
        lines.append(f"container_memory_working_set_bytes{{{labels}}} {working_set}")

    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = collect().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            msg = f"# error: {e}\n".encode()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(msg)

    def log_message(self, *args, **kwargs):  # silence access log
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 9100), Handler).serve_forever()
