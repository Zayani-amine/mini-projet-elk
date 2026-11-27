import os
import urllib.error
from datetime import datetime, timedelta, timezone

from app.services.elasticsearch_client import ElasticsearchError, post_json
from app.utils.cache import cached_value

SEARCH_INDEX_PATTERN = os.environ.get("SEARCH_INDEX_PATTERN", "sb-logs-*,logs-*")
MAINTENANCE_INDEX_PATTERN = os.environ.get(
    "MAINTENANCE_INDEX_PATTERN", "sb-logs-maintenance-*,logs-maintenance"
)
WINDOW_TEMPERATURE_SECONDS = 7 * 24 * 3600
WINDOW_ALERTS_SECONDS = 24 * 3600
WINDOW_ENERGY_SECONDS = 60
WINDOW_OCCUPANCY_SECONDS = 7 * 24 * 3600


class DashboardBackendError(RuntimeError):
    pass


def _search(index_pattern, body):
    try:
        return post_json("/" + index_pattern + "/_search", body)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise DashboardBackendError("Elasticsearch query failed: %s" % exc) from exc
    except (ElasticsearchError, ValueError) as exc:
        raise DashboardBackendError(str(exc)) from exc


def _utc_now():
    return datetime.now(timezone.utc)


def _iso(value):
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _window(seconds, now):
    return {
        "from": _iso(now - timedelta(seconds=seconds)),
        "to": _iso(now),
        "duration_seconds": seconds,
    }


def _timestamp_range(window):
    return {
        "range": {
            "@timestamp": {
                "gte": window["from"],
                "lte": window["to"],
                "format": "strict_date_time_no_millis",
            }
        }
    }


def _buckets(payload, name):
    if not payload:
        return []
    return payload.get("aggregations", {}).get(name, {}).get("buckets", [])


def _rounded(value):
    if value is None:
        return None
    return round(float(value), 2)


def _parse_timestamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_seconds(value, now):
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds()))


def fetch_temperature_avg(now):
    window = _window(WINDOW_TEMPERATURE_SECONDS, now)
    payload = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"measure": "temperature"}},
                        _timestamp_range(window),
                    ]
                }
            },
            "aggs": {
                "global_avg": {"avg": {"field": "value"}},
                "by_zone": {
                    "terms": {"field": "zone", "size": 20},
                    "aggs": {"avg_value": {"avg": {"field": "value"}}},
                },
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
    global_avg = None
    if payload:
        global_avg = _rounded(
            payload.get("aggregations", {}).get("global_avg", {}).get("value")
        )
    meta = {
        "window": window,
        "unit": "°C",
        "global_avg": global_avg,
        "status": "ok" if global_avg is not None else "no_data",
    }
    return result, meta


def fetch_critical_alerts_24h(now):
    window = _window(WINDOW_ALERTS_SECONDS, now)
    payload = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"severity": "critical"}},
                        _timestamp_range(window),
                    ]
                }
            },
            "aggs": {
                "per_hour": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": "1h",
                        "format": "strict_date_time_no_millis",
                        "time_zone": "UTC",
                        "min_doc_count": 0,
                        "extended_bounds": {"min": window["from"], "max": window["to"]},
                    }
                }
            },
        },
    )
    result = []
    for bucket in _buckets(payload, "per_hour"):
        hour = bucket.get("key_as_string", "")
        count = int(bucket.get("doc_count", 0))
        result.append({"hour": hour, "day": hour, "count": count})
    total = sum(item["count"] for item in result)
    meta = {
        "window": window,
        "unit": "alertes",
        "total": total,
        "status": "no_data" if payload is None else "ok",
    }
    return result, meta


def fetch_energy_realtime(now):
    window = _window(WINDOW_ENERGY_SECONDS, now)
    recent = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"exists": {"field": "quantity"}},
                        _timestamp_range(window),
                    ]
                }
            },
            "aggs": {
                "per_minute": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": "1m",
                        "format": "strict_date_time_no_millis",
                        "time_zone": "UTC",
                        "min_doc_count": 0,
                        "extended_bounds": {"min": window["from"], "max": window["to"]},
                    },
                    "aggs": {
                        "by_unit": {
                            "terms": {"field": "unit", "size": 10},
                            "aggs": {"total": {"sum": {"field": "quantity"}}},
                        }
                    },
                },
                "by_unit_total": {
                    "terms": {"field": "unit", "size": 10},
                    "aggs": {"total": {"sum": {"field": "quantity"}}},
                },
            },
        },
    )
    last = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"exists": {"field": "quantity"}},
                        {"term": {"unit": "kWh"}},
                    ]
                }
            },
            "aggs": {"last_reading": {"max": {"field": "@timestamp"}}},
        },
    )
    units = []
    for bucket in _buckets(recent, "by_unit_total"):
        unit = str(bucket.get("key") or "")
        total = _rounded(bucket.get("total", {}).get("value"))
        if unit and total is not None:
            units.append({"unit": unit, "total": total})
    buckets = []
    for minute_bucket in _buckets(recent, "per_minute"):
        minute = minute_bucket.get("key_as_string", "")
        for unit_bucket in _buckets(minute_bucket, "by_unit"):
            total = _rounded(unit_bucket.get("total", {}).get("value"))
            if total is None:
                continue
            buckets.append(
                {
                    "minute": minute,
                    "unit": str(unit_bucket.get("key") or ""),
                    "total": total,
                }
            )
    kwh_values = [
        item["total"]
        for item in units
        if item["unit"].lower() == "kwh" and item["total"] is not None
    ]
    total_kwh = _rounded(sum(kwh_values)) if kwh_values else None
    last_agg = (last or {}).get("aggregations", {}).get("last_reading", {})
    last_reading = _parse_timestamp(
        last_agg.get("value_as_string") or last_agg.get("value")
    )
    last_reading_at = _iso(last_reading)
    age = _age_seconds(last_reading, now)
    stale = total_kwh is None or age is None or age > WINDOW_ENERGY_SECONDS
    status = "no_data" if last_reading is None else ("stale" if stale else "ok")
    value = {
        "window": window,
        "status": status,
        "unit": "kWh",
        "total_kwh": total_kwh,
        "units": units,
        "buckets": buckets,
        "last_reading_at": last_reading_at,
        "age_seconds": age,
        "stale": stale,
    }
    meta = {
        "window": window,
        "unit": "kWh",
        "status": status,
        "total_kwh": total_kwh,
        "last_reading_at": last_reading_at,
        "age_seconds": age,
        "stale": stale,
    }
    return value, meta


def fetch_occupancy_rate(now):
    window = _window(WINDOW_OCCUPANCY_SECONDS, now)
    payload = _search(
        SEARCH_INDEX_PATTERN,
        {
            "size": 0,
            "query": {
                "bool": {
                    "filter": [
                        {"exists": {"field": "occupancy_rate"}},
                        _timestamp_range(window),
                    ]
                }
            },
            "aggs": {
                "global_avg": {"avg": {"field": "occupancy_rate"}},
                "by_room": {
                    "terms": {"field": "room_id", "size": 20},
                    "aggs": {"avg_rate": {"avg": {"field": "occupancy_rate"}}},
                },
            },
        },
    )
    result = []
    for bucket in _buckets(payload, "by_room"):
        result.append(
            {
                "room": bucket.get("key", ""),
                "rate": _rounded(bucket.get("avg_rate", {}).get("value")),
            }
        )
    global_avg = None
    if payload:
        global_avg = _rounded(
            payload.get("aggregations", {}).get("global_avg", {}).get("value")
        )
    meta = {
        "window": window,
        "unit": "%",
        "global_avg": global_avg,
        "status": "ok" if global_avg is not None else "no_data",
    }
    return result, meta


def fetch_maintenance_forecast(now):
    today = now.date().isoformat()
    payload = _search(
        MAINTENANCE_INDEX_PATTERN,
        {
            "size": 100,
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"predicted_failure": True}},
                        {"range": {"estimated_due_date": {"gte": today, "format": "yyyy-MM-dd"}}},
                    ]
                }
            },
            "sort": [{"@timestamp": "desc"}],
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
    for hit in (payload or {}).get("hits", {}).get("hits", []):
        source = dict(hit.get("_source") or {})
        item = {
            "equipment_id": source.get("equipment_id", ""),
            "equipment_type": source.get("equipment_type", ""),
            "wear_level": _rounded(source.get("wear_level")),
            "predicted_failure": bool(source.get("predicted_failure")),
            "estimated_due_date": source.get("estimated_due_date"),
            "timestamp": source.get("@timestamp"),
        }
        identity = item["equipment_id"] or item["timestamp"]
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    result.sort(
        key=lambda item: (
            item.get("estimated_due_date") or "9999-12-31",
            item.get("equipment_id") or "",
        )
    )
    meta = {
        "window": {"from": today, "to": None, "duration_days": None},
        "status": "no_data" if payload is None else "ok",
        "dedupe": "latest_prediction_per_equipment",
    }
    return result, meta


KPI_SOURCES = (
    ("temperature_avg", "elk:kpi:v2:temperature_avg", 60, fetch_temperature_avg),
    ("critical_alerts_24h", "elk:kpi:v2:critical_alerts_24h", 60, fetch_critical_alerts_24h),
    ("energy_realtime", "elk:kpi:v2:energy_realtime", 10, fetch_energy_realtime),
    ("occupancy_rate", "elk:kpi:v2:occupancy_rate", 60, fetch_occupancy_rate),
    ("maintenance_forecast", "elk:kpi:v2:maintenance_forecast", 300, fetch_maintenance_forecast),
)


def _cached_kpi(key, ttl, producer):
    def produce():
        produced_at = _utc_now()
        value, meta = producer(produced_at)
        return {"generated_at": _iso(produced_at), "value": value, "meta": meta}

    envelope, hit = cached_value(key, ttl, produce)
    if isinstance(envelope, dict) and "value" in envelope and "meta" in envelope:
        value = envelope["value"]
        meta = dict(envelope.get("meta") or {})
        meta["generated_at"] = envelope.get("generated_at")
    else:
        value = envelope
        meta = {"generated_at": None}
    meta["cache_hit"] = hit
    return value, meta, hit


def build_stats():
    now = _utc_now()
    data = {}
    kpi_meta = {}
    hits = []
    for name, key, ttl, producer in KPI_SOURCES:
        value, meta, hit = _cached_kpi(key, ttl, producer)
        data[name] = value
        kpi_meta[name] = meta
        hits.append(hit)
    data["critical_alerts_daily"] = data["critical_alerts_24h"]
    data["cache_hit"] = all(hits)
    data["meta"] = {
        "generated_at": _iso(now),
        "cache_hit": all(hits),
        "kpis": kpi_meta,
    }
    return data


def build_maintenance_forecast():
    items, meta, hit = _cached_kpi(
        "elk:kpi:v2:maintenance_forecast", 300, fetch_maintenance_forecast
    )
    return {
        "items": items,
        "count": len(items),
        "cache_hit": hit,
        "meta": meta,
    }
