#!/usr/bin/env bash
set -euo pipefail

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
ES_USER="${ELASTIC_USERNAME:-elastic}"
: "${ELASTIC_PASSWORD:?Définir ELASTIC_PASSWORD (voir .env)}"

create_view() {
  local view_id="$1"
  local title="$2"
  local status

  status="$(curl -sS -o /dev/null -w '%{http_code}' -u "$ES_USER:$ELASTIC_PASSWORD" "$KIBANA_URL/api/data_views/data_view/$view_id")"

  if [ "$status" = "200" ]; then
    echo "Data view $view_id already exists"
    return 0
  fi

  if [ "$status" != "404" ]; then
    echo "Unexpected Kibana response for $view_id: $status" >&2
    exit 1
  fi

  local payload
  payload="$(printf '{"data_view":{"id":"%s","name":"%s","title":"%s","timeFieldName":"@timestamp","allowNoIndex":false}}' "$view_id" "$title" "$title")"

  curl -sS --fail-with-body -u "$ES_USER:$ELASTIC_PASSWORD" \
    -X POST "$KIBANA_URL/api/data_views/data_view" \
    -H 'kbn-xsrf: true' \
    -H 'Content-Type: application/json' \
    -d "$payload"
  echo
}

create_view "logs-*" "logs-*"
create_view "sb-logs-*" "sb-logs-*"
