#!/usr/bin/env bash
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
ES_USER="${ELASTIC_USERNAME:-elastic}"
: "${ELASTIC_PASSWORD:?Définir ELASTIC_PASSWORD (voir .env)}"

status="$(curl -sS -o /dev/null -w '%{http_code}' -u "$ES_USER:$ELASTIC_PASSWORD" "$KIBANA_URL/api/data_views/data_view/logs-*")"

if [ "$status" = "200" ]; then
  echo "Data view logs-* already exists"
  exit 0
fi

if [ "$status" != "404" ]; then
  echo "Unexpected Kibana response: $status" >&2
  exit 1
fi

curl -sS --fail-with-body -u "$ES_USER:$ELASTIC_PASSWORD" \
  -X POST "$KIBANA_URL/api/data_views/data_view" \
  -H 'kbn-xsrf: true' \
  -H 'Content-Type: application/json' \
  -d '{"data_view":{"id":"logs-*","name":"logs-*","title":"logs-*","timeFieldName":"@timestamp","allowNoIndex":false}}'
echo
