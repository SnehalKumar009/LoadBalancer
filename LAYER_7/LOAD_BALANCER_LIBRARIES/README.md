# Load Balancer PoC (Spring Boot + Maven + Docker)

This PoC runs:

- 4 Spring Boot backend app containers (`app1`..`app4`)
- A pluggable load balancer entrypoint — **Apache Traffic Server** by default,
  **NGINX** as a drop-in alternative (see *Swapping load balancers* below)
- `ats-exporter` sidecar that translates ATS `/_stats` JSON into Prometheus metrics
- k6 load generator container (`traffic`)
- Prometheus + Grafana for monitoring
- cAdvisor for container-level metrics
- netshoot toolbox for packet/network debugging

## Architecture

Client / k6 -> LB (`localhost:8088`) -> `app1|app2|app3|app4` (port 8080)

The active LB container exposes itself on the Docker network alias **`lb`**, so
all k6 scripts target `http://lb:8080/` and work unchanged across LBs.

### How load balancing works (ATS 10.x)

The 4 app containers share a Docker network **alias `backend`**, so Docker DNS
returns all four container IPs for the name `backend`. ATS remaps every inbound
request to `http://backend:8080/` and its HostDB **strict round-robin** spreads
requests evenly across those A-records.

## Project Files

- `docker-compose.yml`: full multi-container stack
- `Apache_Traffic_Server/`: ATS configs (`records.yaml`, `remap.config`,
  `plugin.config`, `json-exporter.yml`)
- `Nginx/`: NGINX config (`nginx.conf`) — used when swapping to NGINX
- `k6/`: smoke/load/failover scripts (all hit `http://lb:8080/`)
- `prometheus/prometheus.yml`: scrape jobs
- `grafana/`: auto-provisioned datasource and dashboard
- `scripts/distribution-check.ps1`: quick hit-distribution check from host
- `pom.xml`: Maven dependencies and build

## Swapping load balancers

Only one LB can run at a time (both bind host ports `8088` and `8081`).

In `docker-compose.yml`:

1. Comment out the `ats-lb` **and** `ats-exporter` blocks.
2. Uncomment the `nginx-lb` (and optionally `nginx-exporter`) blocks.

In `prometheus/prometheus.yml`:

3. Comment out the `ats` scrape job.
4. Uncomment the `nginx` scrape job (only if you uncommented `nginx-exporter`).

Then `docker compose up -d --force-recreate`. The k6 scripts and
`distribution-check.ps1` need no changes — they target `http://lb:8080/` /
`http://localhost:8088/` which both LBs serve.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Java 21
- Maven 3.9+

## 1) Build Spring Boot jar

```powershell
mvn clean package
```

### Offline build (Ubuntu / pre-populated ~/.m2)

This project is pinned to **Spring Boot 3.2.4**, chosen because every required
dependency (web, actuator, `micrometer-registry-prometheus` 1.12.4, starter-test)
is already present in the local Maven repository (`~/.m2`). To build without network
access:

```bash
mvn -o clean package
```

If the first offline build fails only because the parent/BOM POMs
(`spring-boot-starter-parent`, `spring-boot-dependencies`) are not yet in `~/.m2`,
run a single online build to fetch just those POMs, then switch back to `-o`:

```bash
mvn clean package      # one-time, fetches missing POMs only
mvn -o clean package   # fully offline thereafter
```

## 2) Start stack

```powershell
docker compose up -d --build
```

> **Important:** Only `app1` has a `build:` section and it produces the shared
> image `ats-l4-poc-app:local` used by `app2..app4`. If you run `docker compose up -d`
> before that image exists, Compose tries to *pull* it and fails with
> `pull access denied for ats-l4-poc-app`. Always build first (`--build`), or run
> `docker compose build app1` once.

## Verify on Linux / bash

The PowerShell scripts below are Windows-oriented. On Linux use these instead.

> **Corporate-proxy gotcha:** if your environment injects `HTTP_PROXY`/`HTTPS_PROXY`
> (e.g. a `*.cisco.com` proxy), in-container HTTP calls get hijacked and backends
> look broken. Always pass `curl --noproxy '*'`. The `traffic` (k6) service already
> sets `NO_PROXY` for the internal hostnames in `docker-compose.yml`.

```bash
# Container status
docker compose ps

# Load distribution through ATS (should be ~even across app1..app4)
for i in $(seq 1 40); do
  curl -s --noproxy '*' http://localhost:8088/ | grep -o '"appId":"[^"]*"'
done | sort | uniq -c

# ATS stats, Prometheus targets, Grafana health
curl -s --noproxy '*' http://localhost:8081/_stats | head
curl -s --noproxy '*' http://localhost:9090/api/v1/targets?state=active
curl -s --noproxy '*' http://localhost:3000/api/health

# k6 (container runs `sleep infinity`, so call k6 explicitly)
docker compose exec -T traffic k6 run /scripts/smoke.js
docker compose exec -T traffic k6 run /scripts/load.js
```

## 3) Verify ATS and apps

```powershell
Invoke-RestMethod -Uri "http://localhost:8088/" -Method Get
.
\scripts\distribution-check.ps1
```

## 4) Run load tests

```powershell
docker compose run --rm traffic run /scripts/smoke.js
docker compose run --rm traffic run /scripts/load.js
```

## 5) Failover test

In one terminal:

```powershell
docker compose run --rm traffic run /scripts/failover.js
```

In another terminal during test:

```powershell
docker compose stop app3
Start-Sleep -Seconds 20
docker compose start app3
```

## Monitor During Test

- Grafana: `http://localhost:3000` (admin/admin)
- Prometheus: `http://localhost:9090`
- cAdvisor: `http://localhost:8089`
- ATS stats endpoint: `http://localhost:8081/_stats`

## Useful Diagnostics

```powershell
docker compose logs -f ats-lb
docker compose exec netshoot sh -c "tcpdump -i any host ats-lb and tcp"
```

## Notes

- ATS in this PoC is configured as a reverse proxy and load-balances HTTP traffic
  across `app1..app4` via a shared Docker network alias (`backend`) plus ATS HostDB
  strict round-robin selection.
- This demonstrates balancing behavior for HTTP traffic. For strict raw TCP L4 behavior, compare with a dedicated L4 proxy mode tool.
- The load balancer uses the official `trafficserver/trafficserver` image (ATS 10.x).
  ATS 10 replaced the legacy `records.config` with `records.yaml`, and this image
  reads its config from `/opt/etc/trafficserver`. Both are reflected in
  `docker-compose.yml` and the `Apache_Traffic_Server/` folder.

