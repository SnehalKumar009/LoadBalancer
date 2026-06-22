# Apache Traffic Server Load Balancer PoC (Spring Boot + Maven + Docker)

This PoC runs:

- 4 Spring Boot backend app containers (`app1`..`app4`)
- Apache Traffic Server (`ats-lb`) as load balancer entrypoint
- k6 load generator container (`traffic`)
- Prometheus + Grafana for monitoring
- cAdvisor for container-level metrics
- netshoot toolbox for packet/network debugging

## Architecture

Client / k6 -> ATS (`localhost:8088`) -> `app1|app2|app3|app4` (port 8080)

## Project Files

- `docker-compose.yml`: full multi-container stack
- `ats/`: ATS configs (`records.yaml`, `remap.config`, `parent.config`, `plugin.config`)
- `k6/`: smoke/load/failover scripts
- `prometheus/prometheus.yml`: scrape jobs
- `grafana/`: auto-provisioned datasource and dashboard
- `scripts/distribution-check.ps1`: quick hit-distribution check from host
- `pom.xml`: Maven dependencies and build

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

- ATS in this PoC is configured as reverse proxy with parent round-robin selection.
- This demonstrates balancing behavior for HTTP traffic. For strict raw TCP L4 behavior, compare with a dedicated L4 proxy mode tool.
- The load balancer uses the official `trafficserver/trafficserver` image (ATS 10.x).
  ATS 10 replaced the legacy `records.config` with `records.yaml`, and this image
  reads its config from `/opt/etc/trafficserver`. Both are reflected in
  `docker-compose.yml` and the `ats/` folder.

