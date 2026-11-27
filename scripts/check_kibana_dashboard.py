import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NDJSON = ROOT / "kibana/saved_objects/elk-dashboard.ndjson"
SETUP = ROOT / "kibana/setup_data_view.sh"
IMPORT = ROOT / "kibana/import_dashboard.sh"
README = ROOT / "README.md"
SCHEMAS = ROOT / "docs/schemas_README.md"

DATA_VIEW = "sb-logs-*,logs-*"
LAYOUT_JSON = [
    {"i": "panel_0", "x": 0, "y": 0, "w": 24, "h": 15},
    {"i": "panel_1", "x": 24, "y": 0, "w": 24, "h": 15},
    {"i": "panel_2", "x": 0, "y": 15, "w": 24, "h": 15},
    {"i": "panel_3", "x": 24, "y": 15, "w": 24, "h": 15},
    {"i": "panel_4", "x": 0, "y": 30, "w": 48, "h": 15},
]
VISUALIZATIONS = {
    "smart-building-temperature-zone-heure": "Température moyenne · 7 j (°C)",
    "smart-building-alertes-critiques-jour": "Alertes critiques · 24 h",
    "smart-building-energie-temps-reel": "Consommation d'énergie (kWh) · 7 j",
    "smart-building-occupation-7d": "Occupation moyenne par salle · 7 j (%)",
    "smart-building-maintenance-future": "Prévisions de maintenance à venir",
}


def fail(message):
    raise SystemExit(message)


def load_objects():
    lines = [line for line in NDJSON.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 7:
        fail("Kibana NDJSON must contain exactly 7 objects")
    objects = []
    for line in lines:
        try:
            objects.append(json.loads(line))
        except json.JSONDecodeError as error:
            fail("Invalid Kibana NDJSON: %s" % error)
    counts = {}
    for obj in objects:
        counts[obj.get("type")] = counts.get(obj.get("type"), 0) + 1
    if counts != {"index-pattern": 1, "visualization": 5, "dashboard": 1}:
        fail("Unexpected Kibana object counts: %s" % counts)
    return objects


def check_data_view(obj):
    if obj.get("id") != DATA_VIEW or obj.get("type") != "index-pattern":
        fail("Combined data view object is incorrect")
    attributes = obj.get("attributes", {})
    if attributes.get("title") != DATA_VIEW or attributes.get("name") != DATA_VIEW:
        fail("Combined data view title is incorrect")
    if attributes.get("timeFieldName") != "@timestamp" or attributes.get("allowNoIndex") is not False:
        fail("Combined data view time settings are incorrect")


def check_visualization(obj):
    object_id = obj.get("id")
    if object_id not in VISUALIZATIONS:
        fail("Unexpected visualization id: %s" % object_id)
    attributes = obj.get("attributes", {})
    if attributes.get("title") != VISUALIZATIONS[object_id]:
        fail("Visualization title is incorrect: %s" % object_id)
    references = obj.get("references", [])
    if references != [{
        "id": DATA_VIEW,
        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
        "type": "index-pattern",
    }]:
        fail("Visualization must reference the combined data view: %s" % object_id)
    search = json.loads(attributes["kibanaSavedObjectMeta"]["searchSourceJSON"])
    filters = search.get("filter", [])
    if not filters:
        fail("Visualization is missing required filters: %s" % object_id)
    for item in filters:
        if item.get("meta", {}).get("index") != DATA_VIEW:
            fail("Visualization filter uses the wrong index: %s" % object_id)
    state = json.loads(attributes["visState"])
    aggs = state.get("aggs", [])
    if not aggs:
        fail("Visualization is missing aggregations: %s" % object_id)
    return search, filters, state


def check_visualization_semantics(objects):
    by_id = {obj.get("id"): obj for obj in objects if obj.get("type") == "visualization"}
    for object_id in VISUALIZATIONS:
        if object_id not in by_id:
            fail("Missing visualization: %s" % object_id)

    search, filters, state = check_visualization(by_id["smart-building-temperature-zone-heure"])
    vis_dump = json.dumps(state, ensure_ascii=False)
    filter_dump = json.dumps(filters, ensure_ascii=False)
    for marker in ('"field": "value"', '"interval": "1d"', '"min_doc_count": 0', '"field": "zone"'):
        if marker not in vis_dump:
            fail("Temperature visualization is missing marker: %s" % marker)
    for marker in ("temperature", "°C", "now-7d"):
        if marker not in filter_dump:
            fail("Temperature visualization filter is missing marker: %s" % marker)

    search, filters, state = check_visualization(by_id["smart-building-alertes-critiques-jour"])
    vis_dump = json.dumps(state, ensure_ascii=False)
    filter_dump = json.dumps(filters, ensure_ascii=False)
    for marker in ('"type": "count"', '"interval": "1h"', '"min_doc_count": 0'):
        if marker not in vis_dump:
            fail("Alerts visualization is missing marker: %s" % marker)
    for marker in ("critical", "now-24h"):
        if marker not in filter_dump:
            fail("Alerts visualization filter is missing marker: %s" % marker)

    search, filters, state = check_visualization(by_id["smart-building-energie-temps-reel"])
    vis_dump = json.dumps(state, ensure_ascii=False)
    filter_dump = json.dumps(filters, ensure_ascii=False)
    for marker in ('"field": "quantity"', '"type": "sum"', '"interval": "1h"', '"min_doc_count": 0'):
        if marker not in vis_dump:
            fail("Energy visualization is missing marker: %s" % marker)
    for marker in ("kWh", "quantity"):
        if marker not in filter_dump:
            fail("Energy visualization filter is missing marker: %s" % marker)
    if '"query": "m3"' in filter_dump or "water" in filter_dump:
        fail("Energy visualization must exclude water")
    if '"interval": "1m"' in vis_dump:
        fail("Energy visualization must not use 1-minute buckets")
    if "now-1m" in filter_dump or '"key": "@timestamp"' in filter_dump:
        fail("Energy visualization must follow the dashboard time range")

    search, filters, state = check_visualization(by_id["smart-building-occupation-7d"])
    vis_dump = json.dumps(state, ensure_ascii=False)
    filter_dump = json.dumps(filters, ensure_ascii=False)
    for marker in ('"field": "occupancy_rate"', '"interval": "1d"'):
        if marker not in vis_dump:
            fail("Occupancy visualization is missing marker: %s" % marker)
    for marker in ("occupancy_rate", "now-7d"):
        if marker not in filter_dump:
            fail("Occupancy visualization filter is missing marker: %s" % marker)

    search, filters, state = check_visualization(by_id["smart-building-maintenance-future"])
    vis_dump = json.dumps(state, ensure_ascii=False)
    filter_dump = json.dumps(filters, ensure_ascii=False)
    description = by_id["smart-building-maintenance-future"]["attributes"].get("description", "")
    for marker in ('"type": "top_hits"', '"size": 1', '"@timestamp"', "estimated_due_date"):
        if marker not in vis_dump:
            fail("Maintenance visualization is missing marker: %s" % marker)
    for marker in ("predicted_failure", "estimated_due_date"):
        if marker not in filter_dump:
            fail("Maintenance visualization filter is missing marker: %s" % marker)
    if "latest_prediction_per_equipment" not in description:
        fail("Maintenance visualization must document latest per-equipment dedupe")


def check_dashboard(obj):
    if obj.get("type") != "dashboard" or obj.get("id") != "smart-building-iot":
        fail("Main dashboard object is missing")
    attributes = obj.get("attributes", {})
    if attributes.get("timeRestore") is not True:
        fail("Dashboard timeRestore is disabled")
    if attributes.get("timeFrom") != "now-7d" or attributes.get("timeTo") != "now":
        fail("Dashboard time range is incorrect")
    refresh = attributes.get("refreshInterval", {})
    if refresh.get("pause") is not False or refresh.get("value") != 60000:
        fail("Dashboard refresh interval is incorrect")
    panels = json.loads(attributes["panelsJSON"])
    actual = [panel["gridData"] for panel in panels]
    for expected in LAYOUT_JSON:
        if expected not in actual:
            fail("Dashboard panel is missing: %s" % expected)
    if len(actual) != len(LAYOUT_JSON):
        fail("Dashboard has unexpected panel count")
    expected_refs = [
        {"id": object_id, "name": "panel_%d" % index, "type": "visualization"}
        for index, object_id in enumerate(VISUALIZATIONS)
    ]
    if obj.get("references") != expected_refs:
        fail("Dashboard visualization references are incorrect")


def check_scripts_and_docs(objects):
    setup = SETUP.read_text(encoding="utf-8")
    if 'create_view "sb-logs-*,logs-*" "sb-logs-*,logs-*"' not in setup:
        fail("setup_data_view.sh does not create the combined data view")
    if "urllib.parse.quote" not in setup:
        fail("setup_data_view.sh does not encode data view ids")
    import_script = IMPORT.read_text(encoding="utf-8")
    for marker in ("success", "successCount", "warnings", "%{http_code}"):
        if marker not in import_script:
            fail("import_dashboard.sh is missing response validation: %s" % marker)
    raw = NDJSON.read_text(encoding="utf-8")
    for marker in ('"id":"logs-*"', '"index":"logs-*"', "temps réel", "par jour", "énergie kWh 1 min"):
        if marker in raw:
            fail("Kibana artifact contains a stale marker: %s" % marker)
    for path in (NDJSON, README, SCHEMAS):
        body = path.read_text(encoding="utf-8")
        if "temps réel" in body or "3 visualisations historiques" in body or "énergie kWh 1 min" in body:
            fail("Misleading Kibana wording remains in %s" % path.name)
    generator = (ROOT / "scripts/generate_logs.py").read_text(encoding="utf-8")
    for marker in ('"water"', '"m3"', "occupancy_rate", "estimated_due_date", "predicted_failure"):
        if marker not in generator:
            fail("Generator is missing field needed by Kibana: %s" % marker)
    template_dir = ROOT / "elasticsearch/templates"
    template_text = "\n".join(path.read_text(encoding="utf-8") for path in template_dir.glob("*.json"))
    for marker in ("unit", "occupancy_rate", "estimated_due_date", "severity", "equipment_id"):
        if marker not in template_text:
            fail("Elasticsearch templates are missing Kibana field: %s" % marker)


objects = load_objects()
by_type = {}
for obj in objects:
    by_type.setdefault(obj.get("type"), []).append(obj)
check_data_view(by_type["index-pattern"][0])
check_visualization_semantics(objects)
check_dashboard(by_type["dashboard"][0])
check_scripts_and_docs(objects)
print("KIBANA_DASHBOARD_OK objects=%d visualizations=%d panels=%d" % (
    len(objects), len(VISUALIZATIONS), len(LAYOUT_JSON)
))
