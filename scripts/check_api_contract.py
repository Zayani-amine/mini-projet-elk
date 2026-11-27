import json
import os
import sys

os.environ["ENABLE_STATUS_POLLER"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.app import create_app
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
    "/privacy",
    "/terms",
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
    "/privacy": {"get"},
    "/terms": {"get"},
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

client = app.test_client()
for path in ("/docs", "/openapi.json"):
    response = client.get(path)
    if response.status_code != 200:
        raise SystemExit("%s returned %s" % (path, response.status_code))
    if "no-store" not in response.headers.get("Cache-Control", ""):
        raise SystemExit("%s is cacheable" % path)

docs_html = client.get("/docs").get_data(as_text=True)

page_bodies = {}
for path in ("/", "/upload", "/search", "/results", "/privacy", "/terms"):
    response = client.get(path)
    body = response.get_data(as_text=True)
    page_bodies[path] = body
    if response.status_code != 200 or "text/html" not in response.content_type:
        raise SystemExit("%s is not serving HTML: %s" % (path, response.status_code))
    if "Smart Building" not in body:
        raise SystemExit("%s is missing the Bootstrap layout" % path)
    if 'rel="icon"' not in body:
        raise SystemExit("%s is missing the favicon link" % path)
    if 'href="/privacy"' not in body or 'href="/terms"' not in body:
        raise SystemExit("%s is missing the legal links" % path)
    if 'alert-status-global' not in body:
        raise SystemExit("%s is missing the alert status region" % path)
    if "Made with AI" in body or "Made with IA" in body:
        raise SystemExit("%s contains a Made with AI tag" % path)
    if "\u2014" in body:
        raise SystemExit("%s contains an em dash" % path)

dashboard_body = page_bodies["/"]
for marker in ("alerts-dot", "alerts-chart-dot", "alerts-headline-dot", "nav-alert-dot"):
    if marker not in dashboard_body:
        raise SystemExit("Dashboard is missing alert dot marker: %s" % marker)

search_body = page_bodies["/search"]
for marker in ("suggest-list", 'aria-autocomplete="list"', 'aria-controls="suggest-list"'):
    if marker not in search_body:
        raise SystemExit("Search page is missing typeahead marker: %s" % marker)

missing_page = client.get("/cette-page-nexiste-pas")
if missing_page.status_code != 404 or "Page introuvable" not in missing_page.get_data(as_text=True):
    raise SystemExit("Frontend 404 page is missing")

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
if "\u2014" in frontend_js:
    raise SystemExit("Frontend JavaScript contains an em dash")

with open("app/static/css/app.css", encoding="utf-8") as handle:
    styles = handle.read()
for marker in ("--elk-glass", "backdrop-filter", ".status-dot"):
    if marker not in styles:
        raise SystemExit("Glassmorphism style is missing: %s" % marker)
if "gradient(" in styles.lower() or "purple" in styles.lower():
    raise SystemExit("Glassmorphism style contains a forbidden background")

print("API_CONTRACT_OK paths=%d" % len(paths))
