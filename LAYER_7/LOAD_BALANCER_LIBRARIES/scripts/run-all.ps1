mvn clean package
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Start-Sleep -Seconds 12

docker compose run --rm traffic run /scripts/smoke.js
docker compose run --rm traffic run /scripts/load.js

