import os
import urllib.error
from datetime import datetime, timedelta, timezone

from app.services.elasticsearch_client import ElasticsearchError, post_json
from app.utils.cache import cached_value

SEARCH_INDEX_PATTERN = os.environ.get("SEARCH_INDEX_PATTERN", "sb-logs-*,logs-*")
MAINTENANCE_INDEX_PATTERN = os.environ.get(
    "MAINTENANCE_INDEX_PATTERN", "sb-logs-maintenance-*,logs-maintenance"
)
DEFAULT_PERIOD = "7d"
MAX_CUSTOM_SECONDS = 90 * 24 * 3600
PERIOD_PRESETS = {
    "1h": {"label": "1 h", "duration_seconds": 3600, "interval": "1m"},
    "24h": {"label": "24 h", "duration_seconds": 24 * 3600, "interval": "1h"},
    "7d": {"label": "7 j", "duration_seconds": 7 * 24 * 3600, "interval": "1h"},
    "30d": {"label": "30 j", "duration_seconds": 30 * 24 * 3600, "interval": "1d"},
}
PERIOD_VALUES = tuple(PERIOD_PRESETS) + ("custom",)


class DashboardBackendError(RuntimeError):
    pass


class PeriodValidationError(ValueError):
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


def _interval_for_seconds(seconds):
    if seconds <= 2 * 3600:
        return "1m"
    if seconds <= 3 * 24 * 3600:
        return "1h"
    return "1d"


def resolve_period(args, now=None):
    now = now or _utc_now()
    args = args or {}
    name = str(args.get("period") or DEFAULT_PERIOD).strip().lower()
    raw_from = args.get("from")
    raw_to = args.get("to")

    if name not in PERIOD_VALUES:
        raise PeriodValidationError("period must be one of: %s" % ", ".join(PERIOD_VALUES))

    if name == "custom":
        parsed_from = _parse_timestamp(raw_from)
        parsed_to = _parse_timestamp(raw_to)
        if parsed_from is None or parsed_to is None:
            raise PeriodValidationError("from and to are required for period=custom")
        duration = int((parsed_to - parsed_from).total_seconds())
        if duration <= 0:
            raise PeriodValidationError("from must be before to")
        if duration > MAX_CUSTOM_SECONDS:
            raise PeriodValidationError("custom period cannot exceed 90 days")
        start = _iso(parsed_from)
        end = _iso(parsed_to)
        return {
            "key": "custom:%s:%s" % (start, end),
            "label": "Personnalisé",
            "from": start,
            "to": end,
            "duration_seconds": duration,
            "interval": _interval_for_seconds(duration),
            "window": {
                "from": start,
                "to": end,
                "duration_seconds": duration,
                "interval": _interval_for_seconds(duration),
            },
        }

    if raw_from or raw_to:
        raise PeriodValidationError("from and to require period=custom")
    preset = PERIOD_PRESETS[name]
    window = _window(preset["duration_seconds"], now)
    window["interval"] = preset["interval"]
    return {
        "key": name,
        "label": preset["label"],
        "from": window["from"],
        "to": window["to"],
        "duration_seconds": preset["duration_seconds"],
        "interval": preset["interval"],
        "window": window,
    }


def _period_spec(period, now):
    if period is None:
        return resolve_period({}, now)
    return period


def fetch_temperature_avg(now, period=None):
    window = _period_spec(period, now)["window"]
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


def fetch_critical_alerts_24h(now, period=None):
    spec = _period_spec(period, now)
    window = spec["window"]
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
                        "fixed_interval": spec["interval"],
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


def fetch_energy_realtime(now, period=None):
    spec = _period_spec(period, now)
    window = spec["window"]
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
                        "fixed_interval": spec["interval"],
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
                        _timestamp_range(window),
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
                    "bucket": minute,
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
    stale = total_kwh is None
    status = "no_data" if total_kwh is None else "ok"
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


def fetch_occupancy_rate(now, period=None):
    window = _period_spec(period, now)["window"]
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


def fetch_maintenance_forecast(now, period=None):
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
    ("temperature_avg", "temperature_avg", 60, fetch_temperature_avg, True),
    ("critical_alerts_24h", "critical_alerts_24h", 60, fetch_critical_alerts_24h, True),
    ("energy_realtime", "energy_realtime", 10, fetch_energy_realtime, True),
    ("occupancy_rate", "occupancy_rate", 60, fetch_occupancy_rate, True),
    ("maintenance_forecast", "maintenance_forecast", 300, fetch_maintenance_forecast, False),
)


def _cached_kpi(key, ttl, callback):
    def produce():
        produced_at = _utc_now()
        value, meta = callback()
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


def build_stats(args=None):
    now = _utc_now()
    period = resolve_period(args, now)
    data = {}
    kpi_meta = {}
    hits = []
    for name, key, ttl, producer, scoped in KPI_SOURCES:
        cache_key = "elk:kpi:v3:" + (period["key"] + ":" if scoped else "") + key

        def produce(producer=producer, scoped=scoped):
            if scoped:
                return producer(now, period)
            return producer(now)

        value, meta, hit = _cached_kpi(cache_key, ttl, produce)
        data[name] = value
        kpi_meta[name] = meta
        hits.append(hit)
    data["critical_alerts_daily"] = data["critical_alerts_24h"]
    data["cache_hit"] = all(hits)
    data["meta"] = {
        "generated_at": _iso(now),
        "cache_hit": all(hits),
        "period": {
            "key": period["key"],
            "label": period["label"],
            "from": period["from"],
            "to": period["to"],
            "duration_seconds": period["duration_seconds"],
            "interval": period["interval"],
        },
        "kpis": kpi_meta,
    }
    return data


def build_maintenance_forecast():
    def produce():
        return fetch_maintenance_forecast(_utc_now())

    items, meta, hit = _cached_kpi(
        "elk:kpi:v3:maintenance_forecast", 300, produce
    )
    return {
        "items": items,
        "count": len(items),
        "cache_hit": hit,
        "meta": meta,
    }
