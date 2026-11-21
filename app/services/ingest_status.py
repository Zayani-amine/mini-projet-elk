import base64
import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from app.services.mongo import get_files_collection

_started = False


def _utc_now():
    return datetime.now(timezone.utc)


def _post_json(path, body):
    host = os.environ.get("ELASTICSEARCH_HOST", "http://elasticsearch:9200").rstrip("/")
    username = os.environ.get("ELASTIC_USERNAME", "elastic")
    password = os.environ.get("ELASTIC_PASSWORD", "")
    request = urllib.request.Request(
        host + path,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = base64.b64encode(("%s:%s" % (username, password)).encode("utf-8"))
    request.add_header("Authorization", "Basic " + token.decode("ascii"))
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def _count_documents(index_pattern, source_file_id):
    try:
        payload = _post_json(
            "/" + index_pattern + "/_count",
            {"query": {"term": {"source_file_id": source_file_id}}},
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return 0
        raise
    return int(payload.get("count", 0))


def _count_indexed_documents(source_file_id):
    return _count_documents("sb-logs-*", source_file_id)


def _count_errors(source_file_id):
    return _count_documents("ingest-errors", source_file_id)


def _first_index_name(source_file_id, log_type):
    payload = _post_json(
        "/sb-logs-*/_search",
        {
            "query": {"term": {"source_file_id": source_file_id}},
            "size": 1,
            "_source": False,
        },
    )
    hits = payload.get("hits", {}).get("hits", [])
    if hits:
        return hits[0].get("_index")
    return "sb-logs-%s-%s" % (log_type, _utc_now().strftime("%Y.%m"))


def _poll_once():
    collection = get_files_collection()
    pending = list(
        collection.find(
            {
                "status": {"$in": ["validated", "ingesting"]},
                "source_file_id": {"$exists": True},
            }
        )
    )
    for document in pending:
        expected = int(document.get("logs_count") or 0)
        if expected <= 0:
            continue
        try:
            indexed = _count_indexed_documents(document["source_file_id"])
            errors = _count_errors(document["source_file_id"])
        except Exception:
            continue

        now = _utc_now()
        if errors > 0:
            collection.update_one(
                {"_id": document["_id"]},
                {
                    "$set": {
                        "status": "failed",
                        "es_index": "ingest-errors",
                        "error_message": "Ingest failed: %d error document(s) in ingest-errors" % errors,
                        "indexed_count": indexed,
                        "updated_at": now,
                    }
                },
            )
            continue

        if indexed < expected:
            continue

        collection.update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    "status": "indexed",
                    "es_index": _first_index_name(document["source_file_id"], document["log_type"]),
                    "indexed_at": now,
                    "indexed_count": indexed,
                    "updated_at": now,
                }
            },
        )


def start_status_poller(app):
    global _started
    if _started:
        return
    _started = True
    interval = int(os.environ.get("STATUS_POLL_INTERVAL", "5"))

    def _run():
        while True:
            try:
                with app.app_context():
                    _poll_once()
            except Exception:
                app.logger.exception("Ingest status poller iteration failed")
            time.sleep(interval)

    threading.Thread(target=_run, name="ingest-status-poller", daemon=True).start()
