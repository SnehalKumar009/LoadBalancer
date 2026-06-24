#!/usr/bin/env bash
# One-command build + run for Linux/Ubuntu.
# Builds the Spring Boot jar FIRST (the app Docker image only packages a pre-built jar),
# then brings up the full stack and runs the k6 smoke + load tests.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Building Spring Boot jar (offline against ~/.m2)..."
# Try a fully offline build first; fall back to online only if POMs/plugins are missing locally.
if ! mvn -o clean package; then
  echo "==> Offline build failed (likely missing parent/BOM POMs). Retrying online once..."
  mvn clean package
fi

echo "==> Confirming jar exists..."
ls -l target/ats-l4-poc-app-*.jar

echo "==> Starting stack..."
docker compose up -d --build

echo "==> Waiting for services to come up..."
sleep 12

echo "==> Running k6 smoke + load tests..."
docker compose run --rm traffic run /scripts/smoke.js
docker compose run --rm traffic run /scripts/load.js

