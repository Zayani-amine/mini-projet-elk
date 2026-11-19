#!/usr/bin/env bash
# Charge les 5 index templates dans Elasticsearch (ELK-11 / T05).
# Variables : ES_URL (défaut http://localhost:9200), ES_USER (défaut elastic),
#             ELASTIC_PASSWORD (obligatoire), CURL_OPTS (ex. "--cacert ca.crt" ou "-k" en https).
set -euo pipefail

ES_URL="${ES_URL:-http://localhost:9200}"
ES_USER="${ES_USER:-elastic}"
: "${ELASTIC_PASSWORD:?Définir ELASTIC_PASSWORD (voir .env)}"
DIR="$(cd "$(dirname "$0")" && pwd)/templates"

for f in "$DIR"/logs-*.json; do
  name="$(basename "$f" .json)"
  echo "PUT _index_template/$name"
  # shellcheck disable=SC2086
  curl -sS --fail-with-body ${CURL_OPTS:-} -u "$ES_USER:$ELASTIC_PASSWORD" \
       -X PUT "$ES_URL/_index_template/$name" \
       -H 'Content-Type: application/json' --data-binary "@$f"
  echo
done
