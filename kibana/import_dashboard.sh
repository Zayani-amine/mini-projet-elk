#!/usr/bin/env bash
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
ES_USER="${ELASTIC_USERNAME:-elastic}"
: "${ELASTIC_PASSWORD:?Définir ELASTIC_PASSWORD (voir .env)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NDJSON_FILE="${SCRIPT_DIR}/saved_objects/elk-dashboard.ndjson"

if [ ! -f "$NDJSON_FILE" ]; then
  echo "Fichier introuvable : $NDJSON_FILE" >&2
  exit 1
fi

curl -sS --fail-with-body -u "$ES_USER:$ELASTIC_PASSWORD" \
  -X POST "$KIBANA_URL/api/saved_objects/_import?overwrite=true" \
  -H 'kbn-xsrf: true' \
  -F "file=@$NDJSON_FILE"
echo
