#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_command docker
require_command python3

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 (docker compose) is required." >&2
  exit 1
fi

if [ ! -f .env ]; then
  cp .env.example .env
  python3 - <<'PY'
from pathlib import Path
import secrets

path = Path(".env")
lines = path.read_text(encoding="utf-8").splitlines()

values = {}
for line in lines:
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()

mongo_user = values.get("MONGO_INITDB_ROOT_USERNAME", "admin")
replacements = {
    "ELASTIC_PASSWORD": secrets.token_hex(16),
    "KIBANA_SYSTEM_PASSWORD": secrets.token_hex(16),
    "MONGO_INITDB_ROOT_PASSWORD": secrets.token_hex(16),
}
mongo_password = replacements["MONGO_INITDB_ROOT_PASSWORD"]
replacements["MONGODB_URI"] = (
    "mongodb://%s:%s@mongodb:27017/?authSource=admin" % (mongo_user, mongo_password)
)

updated = []
for line in lines:
    key = None
    if "=" in line and not line.lstrip().startswith("#"):
        key = line.split("=", 1)[0].strip()
    if key in replacements:
        updated.append("%s=%s" % (key, replacements[key]))
    else:
        updated.append(line)

path.write_text("\n".join(updated) + "\n", encoding="utf-8")
print("Generated .env with fresh secrets.")
PY
fi

if [ "${DEPLOY_DRY_RUN:-0}" = "1" ]; then
  docker compose config --quiet
  echo "DRY_RUN_OK: .env ready and docker-compose.yml is valid."
  exit 0
fi

docker compose up -d --build

expected="elasticsearch kibana logstash mongodb redis webapp"
ready=0

for _ in $(seq 1 90); do
  ready="$(docker compose ps --format json | python3 -c '
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    print(0)
    raise SystemExit(0)

if raw.startswith("["):
    items = json.loads(raw)
else:
    items = [json.loads(line) for line in raw.splitlines() if line.strip()]

expected = {"elasticsearch", "kibana", "logstash", "mongodb", "redis", "webapp"}
found = {}
for item in items:
    name = item.get("Service") or item.get("Name") or ""
    if name in expected:
        found[name] = item

def is_healthy(item):
    health = str(item.get("Health") or "")
    status = str(item.get("Status") or "")
    return health == "healthy" or "(healthy)" in status

print(1 if expected.issubset(found) and all(is_healthy(v) for v in found.values()) else 0)
')"

  if [ "$ready" = "1" ]; then
    break
  fi
  sleep 2
done

docker compose ps

if [ "$ready" != "1" ]; then
  echo "ERROR: all six services did not become healthy in time." >&2
  exit 1
fi

set -a
. ./.env
set +a

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}" bash kibana/setup_data_view.sh
KIBANA_URL="$KIBANA_URL" bash kibana/import_dashboard.sh

echo
echo "Stack deployed."
echo "Kibana: http://localhost:5601"
echo "Flask:  http://localhost:5000/health"
