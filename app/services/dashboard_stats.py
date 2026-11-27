import os
import urllib.error

from app.services.elasticsearch_client import ElasticsearchError, post_json
from app.utils.cache import cached_value

SEARCH_INDEX_PATTERN = os.environ.get("SEARCH_INDEX_PATTERN", "sb-logs-*,logs-*")
MAINTENANCE_INDEX_PATTERN = os.environ.get(
    "MAINTENANCE_INDEX_PATTERN", "sb-logs-maintenance-*,logs-maintenance"
)


class DashboardBackendError(RuntimeError):
    pass


def _search(index_pattern, body):
    try:
        return post_json("/" + index_pattern + "/_search", body)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {"aggregations": {}, "hits": {"hits": []}}
        raise DashboardBackendError("Elasticsearch query failed: %s" % exc) from exc
    except (ElasticsearchError, ValueError) as exc:
        raise DashboardBackendError(str(exc)) from exc


def _buckets(payload, name):
    return payload.get("aggregations", {}).get(name, {}).get("buckets", [])


def _rounded(value):
    if value is None:
        return 0
    return round(float(value), 2)


def fetch_temperature_avg():
    payload = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {"term": {"measure": "temperature"}},
            "aggs": {
                "by_zone": {
                    "terms": {"field": "zone", "size": 20},
                    "aggs": {"avg_value": {"avg": {"field": "value"}}},
                }
            },
        },
    )
    result = []
    for bucket in _buckets(payload, "by_zone"):
        result.append(
            {
                "zone": bucket.get("key", ""),
                "avg": _rounded(bucket.get("avg_value", {}).get("value")),
            }
        )
    return result


def fetch_critical_alerts_daily():
    payload = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {"term": {"severity": "critical"}},
            "aggs": {
                "per_day": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "calendar_interval": "day",
                        "format": "yyyy-MM-dd",
                    }
                }
            },
        },
    )
    result = []
    for bucket in _buckets(payload, "per_day"):
        result.append({"day": bucket.get("key_as_string", ""), "count": int(bucket.get("doc_count", 0))})
    return result


def fetch_energy_realtime():
    payload = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {"exists": {"field": "quantity"}},
            "aggs": {
                "per_minute": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": "1m",
                        "format": "strict_date_time_no_millis",
                    },
                    "aggs": {"total": {"sum": {"field": "quantity"}}},
                }
            },
        },
    )
    result = []
    for bucket in _buckets(payload, "per_minute"):
        result.append(
            {
                "minute": bucket.get("key_as_string", ""),
                "total": _rounded(bucket.get("total", {}).get("value")),
            }
        )
    return result[-30:]


def fetch_occupancy_rate():
    payload = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {"exists": {"field": "occupancy_rate"}},
            "aggs": {
                "by_room": {
                    "terms": {"field": "room_id", "size": 20},
                    "aggs": {"avg_rate": {"avg": {"field": "occupancy_rate"}}},
                }
            },
        },
    )
    result = []
    for bucket in _buckets(payload, "by_room"):
        value = bucket.get("avg_rate", {}).get("value")
        result.append({"room": bucket.get("key", ""), "rate": _rounded(value)})
    return result


def fetch_maintenance_forecast():
    payload = _search(
        MAINTENANCE_INDEX_PATTERN,
        {
            "size": 50,
            "query": {"term": {"predicted_failure": True}},
            "sort": [{"estimated_due_date": "asc"}],
            "_source": [
                "equipment_id",
                "equipment_type",
                "wear_level",
                "predicted_failure",
                "estimated_due_date",
                "@timestamp",
            ],
        },
    )
    result = []
    seen = set()
    for hit in payload.get("hits", {}).get("hits", []):
        source = dict(hit.get("_source") or {})
        item = {
            "equipment_id": source.get("equipment_id", ""),
            "equipment_type": source.get("equipment_type", ""),
            "wear_level": _rounded(source.get("wear_level")),
            "predicted_failure": bool(source.get("predicted_failure")),
            "estimated_due_date": source.get("estimated_due_date"),
            "timestamp": source.get("@timestamp"),
        }
        identity = (item["equipment_id"], item["estimated_due_date"])
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result


KPI_SOURCES = (
    ("temperature_avg", "elk:kpi:temperature_avg", 60, fetch_temperature_avg),
    ("critical_alerts_daily", "elk:kpi:critical_alerts_daily", 60, fetch_critical_alerts_daily),
    ("energy_realtime", "elk:kpi:energy_realtime", 10, fetch_energy_realtime),
    ("occupancy_rate", "elk:kpi:occupancy_rate", 60, fetch_occupancy_rate),
    ("maintenance_forecast", "elk:kpi:maintenance_forecast", 300, fetch_maintenance_forecast),
)


def build_stats():
    data = {}
    hits = []
    for name, key, ttl, producer in KPI_SOURCES:
        value, hit = cached_value(key, ttl, producer)
        data[name] = value
        hits.append(hit)
    data["cache_hit"] = all(hits)
    return data


def build_maintenance_forecast():
    items, hit = cached_value(
        "elk:kpi:maintenance_forecast", 300, fetch_maintenance_forecast
    )
    return {"items": items, "count": len(items), "cache_hit": hit}
