import json
import os
import sys

os.environ["ENABLE_STATUS_POLLER"] = "0"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.app import create_app
from app.services.elasticsearch_search import build_query

app = create_app()
required = {
    "/",
    "/health",
    "/api/v1/upload",
    "/api/v1/files/{file_id}",
    "/api/v1/search",
    "/api/v1/history",
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
    "/api/v1/history": {"get"},
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
if '"fuzziness": "AUTO"' not in json.dumps(fuzzy_query):
    raise SystemExit("Search query is not fuzzy")

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

print("API_CONTRACT_OK paths=%d" % len(paths))
