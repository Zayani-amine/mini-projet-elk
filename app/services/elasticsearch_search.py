import os
from datetime import datetime, timezone

from app.services.elasticsearch_client import ElasticsearchError, post_json
from app.utils.upload_validation import LOG_TYPES

SEARCH_INDEX_PATTERN = os.environ.get("SEARCH_INDEX_PATTERN", "sb-logs-*,logs-*")
SEARCH_FIELDS = [
    "entity_id^3",
    "message.keyword^2",
    "zone",
    "measure",
    "status",
    "severity",
    "rule",
    "equipment_type",
    "energy_type",
]
SORT_VALUES = {"recent": "desc", "oldest": "asc"}


class SearchValidationError(ValueError):
    pass


class SearchBackendError(RuntimeError):
    pass


def _clean(value, name, max_length=256):
    text = str(value or "").strip()
    if len(text) > max_length:
        raise SearchValidationError("%s is too long (max %d characters)" % (name, max_length))
    return text


def _integer(value, name, default, minimum, maximum=None):
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise SearchValidationError("%s must be an integer" % name) from exc
    if number < minimum or (maximum is not None and number > maximum):
        if maximum is None:
            raise SearchValidationError("%s must be at least %d" % (name, minimum))
        raise SearchValidationError("%s must be between %d and %d" % (name, minimum, maximum))
    return number


def _date(value, name):
    text = _clean(value, name, 64)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SearchValidationError("%s must be an ISO-8601 date" % name) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def parse_search_params(args):
    q = _clean(args.get("q"), "q")
    log_type = _clean(args.get("log_type"), "log_type", 64).lower() or None
    if log_type and log_type not in LOG_TYPES:
        raise SearchValidationError("Unknown log_type '%s'" % log_type)

    date_from = _date(args.get("from"), "from")
    date_to = _date(args.get("to"), "to")
    if date_from and date_to and date_from > date_to:
        raise SearchValidationError("from must be before to")

    sort = _clean(args.get("sort"), "sort", 16).lower() or "recent"
    if sort not in SORT_VALUES:
        raise SearchValidationError("Unknown sort '%s'" % sort)

    return {
        "q": q,
        "log_type": log_type,
        "source_file_id": _clean(args.get("source_file_id"), "source_file_id", 128) or None,
        "severity": _clean(args.get("severity"), "severity", 64).lower() or None,
        "zone": _clean(args.get("zone"), "zone", 128) or None,
        "entity_id": _clean(args.get("entity_id"), "entity_id", 128) or None,
        "date_from": date_from,
        "date_to": date_to,
        "page": _integer(args.get("page"), "page", 1, 1),
        "size": _integer(args.get("size"), "size", 20, 1, 100),
        "sort": sort,
    }


def build_query(params):
    must = []
    filters = []
    if params["q"]:
        must.append(
            {
                "multi_match": {
                    "query": params["q"],
                    "fields": SEARCH_FIELDS,
                    "type": "best_fields",
                    "operator": "and",
                }
            }
        )

    for key, field in (
        ("log_type", "log_type"),
        ("source_file_id", "source_file_id"),
        ("severity", "severity"),
        ("zone", "zone"),
        ("entity_id", "entity_id"),
    ):
        if params[key]:
            filters.append({"term": {field: params[key]}})

    if params["date_from"] or params["date_to"]:
        bounds = {}
        if params["date_from"]:
            bounds["gte"] = params["date_from"].isoformat()
        if params["date_to"]:
            bounds["lte"] = params["date_to"].isoformat()
        filters.append({"range": {"@timestamp": bounds}})

    if must or filters:
        return {"bool": {"must": must, "filter": filters}}
    return {"match_all": {}}


def build_history_document(params, result):
    return {
        "created_at": datetime.now(timezone.utc),
        "query": params["q"],
        "filters": {
            "log_types": [params["log_type"]] if params["log_type"] else [],
            "severity": params["severity"],
            "zone": params["zone"],
            "entity_id": params["entity_id"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "source_file_id": params["source_file_id"],
            "size": params["size"],
        },
        "sort": params["sort"],
        "page": params["page"],
        "results_count": result["total"],
        "took_ms": result["took_ms"],
        "cache_hit": False,
    }


def search_logs(params):
    body = {
        "query": build_query(params),
        "from": (params["page"] - 1) * params["size"],
        "size": params["size"],
        "sort": [{"@timestamp": SORT_VALUES[params["sort"]]}],
        "track_total_hits": True,
    }
    try:
        payload = post_json("/" + SEARCH_INDEX_PATTERN + "/_search", body)
    except ElasticsearchError as exc:
        raise SearchBackendError(str(exc)) from exc
    except Exception as exc:
        if getattr(exc, "code", None) == 404:
            payload = {"took": 0, "hits": {"total": {"value": 0}, "hits": []}}
        else:
            raise SearchBackendError("Elasticsearch search failed: %s" % exc) from exc

    hits = payload.get("hits", {})
    total = hits.get("total", {})
    if isinstance(total, dict):
        total = total.get("value", 0)
    results = []
    for hit in hits.get("hits", []):
        source = dict(hit.get("_source") or {})
        source["_index"] = hit.get("_index")
        source["_id"] = hit.get("_id")
        results.append(source)
    return {
        "results": results,
        "total": int(total),
        "page": params["page"],
        "size": params["size"],
        "took_ms": int(payload.get("took", 0)),
    }
