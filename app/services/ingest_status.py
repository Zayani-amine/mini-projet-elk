import base64
import json
import os
import threading
import time
import urllib.request
from datetime import datetime, timezone

from app.services.mongo import get_files_collection

_started = False


def _utc_now():
    return datetime.now(timezone.utc)


def _count_indexed_documents(source_file_id):
    host = os.environ.get("ELASTICSEARCH_HOST", "http://elasticsearch:9200").rstrip("/")
    username = os.environ.get("ELASTIC_USERNAME", "elastic")
    password = os.environ.get("ELASTIC_PASSWORD", "")
    body = json.dumps({"query": {"term": {"source_file_id": source_file_id}}}).encode("utf-8")
    request = urllib.request.Request(
        host + "/logs-*/_count",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    token = base64.b64encode(("%s:%s" % (username, password)).encode("utf-8"))
    request.add_header("Authorization", "Basic " + token.decode("ascii"))
    with urllib.request.urlopen(request, timeout=5) as response:
        payload = json.load(response)
    return int(payload.get("count", 0))


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
        except Exception:
            continue
        if indexed < expected:
            continue
        now = _utc_now()
        collection.update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    "status": "indexed",
                    "es_index": "logs-%s" % document["log_type"],
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
