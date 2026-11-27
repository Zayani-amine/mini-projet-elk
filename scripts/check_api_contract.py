import json
import os
import sys
from datetime import datetime, timezone

os.environ["ENABLE_STATUS_POLLER"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.app import create_app
from app.services import dashboard_stats
from app.services.elasticsearch_search import build_query, build_suggest_query

app = create_app()
required = {
    "/",
    "/health",
    "/api/v1/upload",
    "/api/v1/files/{file_id}",
    "/api/v1/search",
    "/api/v1/suggest",
    "/api/v1/history",
    "/api/v1/stats",
    "/api/v1/maintenance/forecast",
    "/api/v1/logs/export",
    "/api/v1/files",
    "/upload",
    "/search",
    "/results",
}
paths = set(app.spec["paths"])
missing = required - paths
if missing:
    raise SystemExit("Missing OpenAPI paths: %s" % sorted(missing))

expected_methods = {
    "/": {"get"},
    "/health": {"get"},
    "/api/v1/upload": {"post"},
    "/api/v1/files/{file_id}": {"get"},
    "/api/v1/search": {"get"},
    "/api/v1/suggest": {"get"},
    "/api/v1/history": {"get"},
    "/api/v1/stats": {"get"},
    "/api/v1/maintenance/forecast": {"get"},
    "/api/v1/logs/export": {"get"},
    "/api/v1/files": {"get"},
    "/upload": {"get"},
    "/search": {"get"},
    "/results": {"get"},
}
for path, methods in expected_methods.items():
    actual = set(app.spec["paths"][path])
    if not methods <= actual:
        raise SystemExit("Missing OpenAPI methods on %s: %s" % (path, sorted(methods - actual)))
    for method in methods:
        operation = app.spec["paths"][path][method]
        if not operation.get("summary") or not operation.get("tags"):
            raise SystemExit("Undocumented OpenAPI operation: %s %s" % (method.upper(), path))

upload_errors = set(app.spec["paths"]["/api/v1/upload"]["post"]["responses"])
for status in ("400", "413"):
    if status not in upload_errors:
        raise SystemExit("Upload is missing documented response %s" % status)
file_errors = set(app.spec["paths"]["/api/v1/files/{file_id}"]["get"]["responses"])
for status in ("400", "404"):
    if status not in file_errors:
        raise SystemExit("File route is missing documented response %s" % status)
stats_responses = set(app.spec["paths"]["/api/v1/stats"]["get"]["responses"])
for status in ("200", "400", "503"):
    if status not in stats_responses:
        raise SystemExit("Stats route is missing documented response %s" % status)
stats_params = {
    parameter["name"]: parameter["schema"]
    for parameter in app.spec["paths"]["/api/v1/stats"]["get"]["parameters"]
}
if stats_params.get("period", {}).get("enum") != ["1h", "24h", "7d", "30d", "custom"]:
    raise SystemExit("Stats period values are not documented")
for name in ("from", "to"):
    if stats_params.get(name, {}).get("format") != "date-time":
        raise SystemExit("Stats %s date is not documented as date-time" % name)

client = app.test_client()
for path in ("/docs", "/openapi.json"):
    response = client.get(path)
    if response.status_code != 200:
        raise SystemExit("%s returned %s" % (path, response.status_code))
    if "no-store" not in response.headers.get("Cache-Control", ""):
        raise SystemExit("%s is cacheable" % path)

docs_html = client.get("/docs").get_data(as_text=True)

page_bodies = {}
for path in ("/", "/upload", "/search", "/results"):
    response = client.get(path)
    body = response.get_data(as_text=True)
    page_bodies[path] = body
    if response.status_code != 200 or "text/html" not in response.content_type:
        raise SystemExit("%s is not serving HTML: %s" % (path, response.status_code))
    if "Smart Building" not in body:
        raise SystemExit("%s is missing the Bootstrap layout" % path)
    if 'rel="icon"' not in body:
        raise SystemExit("%s is missing the favicon link" % path)
    if 'href="/privacy"' in body or 'href="/terms"' in body:
        raise SystemExit("%s still contains legal links" % path)
    if 'class="brand-mark"' in body:
        raise SystemExit("%s still contains the ELK navbar chip" % path)
    if 'alert-status-global' not in body:
        raise SystemExit("%s is missing the alert status region" % path)
    if 'class="skip-link"' not in body or 'id="main-content"' not in body or 'tabindex="-1"' not in body:
        raise SystemExit("%s is missing the skip link target" % path)
    if "Made with AI" in body or "Made with IA" in body:
        raise SystemExit("%s contains a Made with AI tag" % path)
    if "\u2014" in body:
        raise SystemExit("%s contains an em dash" % path)

dashboard_body = page_bodies["/"]
for marker in ("alerts-dot", "alerts-chart-dot", "alerts-headline-dot", "alerts-action"):
    if marker not in dashboard_body:
        raise SystemExit("Dashboard is missing alert dot marker: %s" % marker)
for marker in (
    "dashboard-period-form",
    "dashboard-period",
    "dashboard-period-summary",
    "dashboard-custom-range",
    "dashboard-period-error",
    'type="datetime-local"',
):
    if marker not in dashboard_body:
        raise SystemExit("Dashboard period selector is missing: %s" % marker)

search_body = page_bodies["/search"]
for marker in (
    "suggest-list",
    'aria-autocomplete="list"',
    'aria-controls="suggest-list"',
    "novalidate",
    "suggest-status",
    "date-error",
    "q-error",
):
    if marker not in search_body:
        raise SystemExit("Search page is missing typeahead or validation marker: %s" % marker)

upload_body = page_bodies["/upload"]
for marker in (
    'role="button"',
    'aria-describedby="upload-formats upload-file-name"',
    'aria-live="polite"',
    "upload-formats",
    "upload-file-name",
    "upload-progress-wrap",
    "upload-history-card",
    "upload-history-list",
    "upload-history-status",
    "upload-history-retry",
):
    if marker not in upload_body:
        raise SystemExit("Upload page is missing accessibility marker: %s" % marker)

missing_page = client.get("/cette-page-nexiste-pas")
if missing_page.status_code != 404 or "Page introuvable" not in missing_page.get_data(as_text=True):
    raise SystemExit("Frontend 404 page is missing")

for path in ("/privacy", "/terms"):
    if client.get(path).status_code != 404:
        raise SystemExit("Legal page still exists: %s" % path)

missing_api = client.get("/api/v1/inconnu")
if missing_api.status_code != 404 or "error" not in missing_api.get_json():
    raise SystemExit("API 404 is not normalized")

export_responses = app.spec["paths"]["/api/v1/logs/export"]["get"]["responses"]
if "200" not in export_responses or "text/csv" not in export_responses["200"]["content"]:
    raise SystemExit("CSV export is not documented")

schema = app.config["HTTP_ERROR_SCHEMA"]
if set(schema["properties"]) != {"error"}:
    raise SystemExit("Unexpected error schema")

fuzzy_query = build_query(
    {
        "q": "temperatur",
        "log_type": None,
        "source_file_id": None,
        "severity": None,
        "zone": None,
        "entity_id": None,
        "date_from": None,
        "date_to": None,
    }
)
fuzzy_dump = json.dumps(fuzzy_query)
for marker in (
    '"fuzziness": "AUTO"',
    '"operator": "and"',
    '"operator": "or"',
    '"boost": 3',
    '"boost": 1',
    '"prefix_length": 1',
):
    if marker not in fuzzy_dump:
        raise SystemExit("Search query is missing fuzzy marker: %s" % marker)

suggest_query = build_suggest_query({"q": "temperatur"})
suggest_dump = json.dumps(suggest_query)
if '"fuzziness": "AUTO"' not in suggest_dump or '"prefix_length": 1' not in suggest_dump:
    raise SystemExit("Suggest query is not fuzzy")

search_parameters = app.spec["paths"]["/api/v1/search"]["get"]["parameters"]
date_formats = {
    parameter["name"]: parameter["schema"].get("format")
    for parameter in search_parameters
    if parameter["name"] in ("from", "to")
}
if date_formats != {"from": "date-time", "to": "date-time"}:
    raise SystemExit("Search dates are not documented as date-time: %s" % date_formats)

q_parameter = next(parameter for parameter in search_parameters if parameter["name"] == "q")
q_example = q_parameter.get("example") or q_parameter.get("schema", {}).get("example")
if q_example != "temperatur":
    raise SystemExit("Search query example is missing: %s" % q_example)

suggest_parameters = app.spec["paths"]["/api/v1/suggest"]["get"]["parameters"]
suggest_formats = {
    parameter["name"]: parameter["schema"].get("format")
    for parameter in suggest_parameters
    if parameter["name"] in ("from", "to")
}
if suggest_formats != {"from": "date-time", "to": "date-time"}:
    raise SystemExit("Suggest dates are not documented as date-time: %s" % suggest_formats)
suggest_q = next(parameter for parameter in suggest_parameters if parameter["name"] == "q")
suggest_q_example = suggest_q.get("example") or suggest_q.get("schema", {}).get("example")
if suggest_q_example != "temperatur":
    raise SystemExit("Suggest query example is missing: %s" % suggest_q_example)

file_description = app.spec["components"]["schemas"]["UploadInput"]["properties"]["file"][
    "description"
]
if ".csv" not in file_description or ".json" not in file_description or ".txt" not in file_description:
    raise SystemExit("Upload file description does not list allowed extensions")

swagger_config = app.config["SWAGGER_UI_CONFIG"]["onComplete"]
for marker in ("showOpenFilePicker", "excludeAcceptAllOption", "datetime-local", "elk-docs-banner"):
    if marker not in swagger_config:
        raise SystemExit("Swagger UI enhancement is missing: %s" % marker)
for marker in ("showOpenFilePicker", "excludeAcceptAllOption", "elk-upload-button", "elk-docs-banner"):
    if marker not in docs_html:
        raise SystemExit("Served Swagger UI is missing: %s" % marker)

with open("app/static/js/app.js", encoding="utf-8") as handle:
    frontend_js = handle.read()
for marker in ("/api/v1/suggest", "AbortController", "aria-activedescendant"):
    if marker not in frontend_js:
        raise SystemExit("Frontend typeahead is missing: %s" % marker)
for marker in ("updateAlertState", "criticalAlertCount", "alert-status-global", "severity-critical"):
    if marker not in frontend_js:
        raise SystemExit("Frontend alert intelligence is missing: %s" % marker)
for marker in (
    "bindDashboardControls",
    "dashboardParamsFromControls",
    "applyDashboardParams",
    "initUploadHistory",
    "chartInstances",
    "cleanLabel",
    "setAriaLabel",
    "'/api/v1/stats?'",
):
    if marker not in frontend_js:
        raise SystemExit("Frontend period or history marker is missing: %s" % marker)
if "\u2014" in frontend_js:
    raise SystemExit("Frontend JavaScript contains an em dash")

with open("app/services/dashboard_stats.py", encoding="utf-8") as handle:
    stats_source = handle.read()
for marker in (
    'DEFAULT_PERIOD = "7d"',
    "MAX_CUSTOM_SECONDS = 90 * 24 * 3600",
    "PERIOD_PRESETS",
    "PERIOD_VALUES",
    "class PeriodValidationError",
    "def resolve_period",
    "def _interval_for_seconds",
    '"fixed_interval": spec["interval"]',
    '"min_doc_count": 0',
    '"global_avg"',
    '"last_reading"',
    '"age_seconds"',
    '"term": {"unit": "kWh"}',
    '"estimated_due_date": {"gte": today',
    '"latest_prediction_per_equipment"',
    "elk:kpi:v3:",
    '"generated_at"',
    '"period": {',
):
    if marker not in stats_source:
        raise SystemExit("Dashboard semantic marker is missing: %s" % marker)
if dashboard_stats._rounded(None) is not None:
    raise SystemExit("Missing dashboard values must not become zero")
fixed_now = datetime(2026, 11, 27, 19, 55, tzinfo=timezone.utc)
if dashboard_stats._window(60, fixed_now)["from"] != "2026-11-27T19:54:00Z":
    raise SystemExit("Dashboard window helper is incorrect")
if dashboard_stats._age_seconds("2026-11-27T19:54:30Z", fixed_now) != 30:
    raise SystemExit("Dashboard age helper is incorrect")
for seconds, expected in ((3600, "1m"), (24 * 3600, "1h"), (30 * 24 * 3600, "1d")):
    if dashboard_stats._interval_for_seconds(seconds) != expected:
        raise SystemExit("Dashboard interval helper is incorrect for %s seconds" % seconds)
if dashboard_stats.DEFAULT_PERIOD != "7d" or dashboard_stats.MAX_CUSTOM_SECONDS != 90 * 24 * 3600:
    raise SystemExit("Dashboard period constants are incorrect")
preset = dashboard_stats.resolve_period({"period": "24h"}, fixed_now)
if preset["from"] != "2026-11-26T19:55:00Z" or preset["to"] != "2026-11-27T19:55:00Z":
    raise SystemExit("Dashboard preset period bounds are incorrect")
if preset["interval"] != "1h" or preset["duration_seconds"] != 24 * 3600:
    raise SystemExit("Dashboard preset period metadata is incorrect")
custom = dashboard_stats.resolve_period(
    {
        "period": "custom",
        "from": "2026-11-26T19:55:00Z",
        "to": "2026-11-27T19:55:00Z",
    },
    fixed_now,
)
if custom["duration_seconds"] != 24 * 3600 or custom["interval"] != "1h":
    raise SystemExit("Dashboard custom period metadata is incorrect")
for invalid_args in (
    {"period": "1y"},
    {"period": "custom"},
    {"period": "custom", "from": "2026-11-27T19:55:00Z", "to": "2026-11-26T19:55:00Z"},
    {"period": "7d", "from": "2026-11-26T19:55:00Z"},
):
    try:
        dashboard_stats.resolve_period(invalid_args, fixed_now)
    except dashboard_stats.PeriodValidationError:
        continue
    raise SystemExit("Invalid period was accepted: %s" % invalid_args)

captured_bodies = []
original_post_json = dashboard_stats.post_json
original_cached_value = dashboard_stats.cached_value


def capture_post_json(path, body, *args, **kwargs):
    captured_bodies.append(body)
    return {"aggregations": {}, "hits": {"total": 0, "hits": []}}


def uncached_value(key, ttl, producer):
    return producer(), False


dashboard_stats.post_json = capture_post_json
dashboard_stats.cached_value = uncached_value
try:
    dashboard_stats.fetch_critical_alerts_24h(fixed_now, preset)
    dashboard_stats.fetch_energy_realtime(fixed_now, preset)
    stats_payload = dashboard_stats.build_stats({"period": "24h"})
    if stats_payload["meta"]["period"]["key"] != "24h":
        raise SystemExit("build_stats did not return the selected period")
finally:
    dashboard_stats.post_json = original_post_json
    dashboard_stats.cached_value = original_cached_value
for body in captured_bodies:
    for aggregation in body.get("aggs", {}).values():
        histogram = aggregation.get("date_histogram")
        if not histogram or "extended_bounds" not in histogram:
            continue
        if histogram.get("format") != "strict_date_time_no_millis":
            raise SystemExit("Extended date bounds must use ISO format")
        if histogram.get("fixed_interval") != "1h":
            raise SystemExit("Histogram did not use the selected period interval")

with open("app/templates/index.html", encoding="utf-8") as handle:
    dashboard_html = handle.read()
with open("app/templates/results.html", encoding="utf-8") as handle:
    results_html = handle.read()
with open("app/templates/upload.html", encoding="utf-8") as handle:
    upload_template = handle.read()
for html, name in ((dashboard_html, "dashboard"), (results_html, "results"), (upload_template, "upload")):
    if "n/d" in html:
        raise SystemExit("%s template still contains an initial n/d placeholder" % name)
for marker in (
    "kpi-temperature-detail",
    "kpi-alerts-detail",
    "kpi-energy-detail",
    "kpi-occupancy-detail",
    "kpi-maintenance-detail",
    "label-temperature",
    "label-alerts-text",
    "label-energy",
    "label-occupancy",
    "dashboard-period-summary",
    "Chargement…",
    "En attente",
):
    if marker not in dashboard_html:
        raise SystemExit("Dashboard template semantic marker is missing: %s" % marker)
for marker in (
    "critical_alerts_24h",
    "global_avg",
    "total_kwh",
    "last_reading_at",
    "age_seconds",
    "energyHasData",
    "formatAge",
    "document(s)",
    "setFieldError",
    "renderChartData",
    "chart-empty-message",
    "MAX_UPLOAD_BYTES",
    "dashboard-retry",
    "results-retry",
    "aria-valuetext",
    "Aucun document pour ces critères.",
):
    if marker not in frontend_js:
        raise SystemExit("Frontend semantic marker is missing: %s" % marker)
for marker in (
    "dashboard-retry",
    "chart-legend",
    "Voir les valeurs du graphique",
    'role="img"',
    'scope="col"',
    "chart-occupancy-data",
):
    if marker not in dashboard_html:
        raise SystemExit("Dashboard accessibility marker is missing: %s" % marker)
for marker in (
    "results-retry",
    '<caption class="visually-hidden">',
    'scope="col"',
    'role="status"',
    "page-label",
):
    if marker not in results_html:
        raise SystemExit("Results accessibility marker is missing: %s" % marker)
for forbidden in ("temps réel", "Dernière minute relevée", "Dernier jour relevé", "résultat(s)", "occurrence(s)", "Aucun résultat pour ces critères."):
    if forbidden in frontend_js or forbidden in dashboard_html or forbidden in results_html:
        raise SystemExit("Misleading frontend wording remains: %s" % forbidden)

with open("app/static/css/app.css", encoding="utf-8") as handle:
    styles = handle.read()
for marker in (
    "color-scheme: light",
    "--elk-surface",
    "--elk-radius-card",
    ".status-dot",
    ".skip-link",
    ".chart-empty-message",
    ".chart-table",
    ":focus-visible",
    "prefers-reduced-motion",
):
    if marker not in styles:
        raise SystemExit("Modern light style is missing: %s" % marker)
lowered_styles = styles.lower()
for marker in ("backdrop-filter", "--elk-glass", "gradient(", "purple", ".brand-mark"):
    if marker in lowered_styles:
        raise SystemExit("Modern light style contains a forbidden marker: %s" % marker)

print("API_CONTRACT_OK paths=%d" % len(paths))
