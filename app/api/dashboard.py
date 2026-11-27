import csv
import io

from apiflask import APIBlueprint
from flask import Response, jsonify, request
from pymongo.errors import PyMongoError

from app.api.errors import ERROR_RESPONSE, error_response
from app.api.files import _serialize_file
from app.services.dashboard_stats import (
    DashboardBackendError,
    build_maintenance_forecast,
    build_stats,
)
from app.services.elasticsearch_search import (
    SearchBackendError,
    SearchValidationError,
    parse_search_params,
    search_logs,
)
from app.services.mongo import get_files_collection

api_v1_dashboard = APIBlueprint(
    "api_v1_dashboard",
    __name__,
    url_prefix="/api/v1",
    tag="Tableau de bord",
)

SUCCESS_JSON = {
    "description": "Réponse JSON",
    "content": {"application/json": {"schema": {"type": "object"}}},
}

CSV_RESPONSE = {
    "description": "Export CSV",
    "content": {"text/csv": {"schema": {"type": "string"}}},
}


def _pagination(args):
    try:
        page = int(args.get("page", 1))
        size = int(args.get("size", 20))
    except (TypeError, ValueError) as exc:
        raise SearchValidationError("page and size must be integers") from exc
    if page < 1:
        raise SearchValidationError("page must be at least 1")
    if size < 1 or size > 100:
        raise SearchValidationError("size must be between 1 and 100")
    return page, size


@api_v1_dashboard.get("/stats")
@api_v1_dashboard.doc(
    summary="Lire les indicateurs du tableau de bord",
    tags=["Tableau de bord"],
    description="Agrégations Elasticsearch des 5 KPI, mises en cache Redis.",
    responses={200: SUCCESS_JSON, 503: ERROR_RESPONSE},
)
def stats():
    try:
        return jsonify(build_stats()), 200
    except DashboardBackendError as exc:
        return error_response("ELASTICSEARCH_UNAVAILABLE", str(exc), 503)


@api_v1_dashboard.get("/maintenance/forecast")
@api_v1_dashboard.doc(
    summary="Prévisions de maintenance",
    tags=["Tableau de bord"],
    description="Équipements avec panne prédite, triés par échéance.",
    responses={200: SUCCESS_JSON, 503: ERROR_RESPONSE},
)
def maintenance_forecast():
    try:
        return jsonify(build_maintenance_forecast()), 200
    except DashboardBackendError as exc:
        return error_response("ELASTICSEARCH_UNAVAILABLE", str(exc), 503)


@api_v1_dashboard.get("/logs/export")
@api_v1_dashboard.doc(
    summary="Exporter les résultats de recherche en CSV",
    tags=["Tableau de bord"],
    description="Exporte jusqu'à 10 000 logs correspondant aux filtres de recherche.",
    responses={200: CSV_RESPONSE, 400: ERROR_RESPONSE, 503: ERROR_RESPONSE},
)
def logs_export():
    try:
        params = parse_search_params(request.args, max_size=10000)
    except SearchValidationError as exc:
        return error_response("INVALID_SEARCH_PARAMS", str(exc), 400)
    params["page"] = 1

    try:
        result = search_logs(params)
    except SearchBackendError as exc:
        return error_response("ELASTICSEARCH_UNAVAILABLE", str(exc), 503)

    rows = result["results"]
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    if not columns:
        columns = ["@timestamp", "_index", "_id", "message"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([str(row.get(column, "")) for column in columns])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs-export.csv"},
    )


@api_v1_dashboard.get("/files")
@api_v1_dashboard.doc(
    summary="Lister les fichiers déposés",
    tags=["Tableau de bord"],
    description="Retourne les fichiers triés du plus récent au plus ancien.",
    responses={200: SUCCESS_JSON, 400: ERROR_RESPONSE, 503: ERROR_RESPONSE},
)
def list_files():
    try:
        page, size = _pagination(request.args)
    except SearchValidationError as exc:
        return error_response("INVALID_PAGINATION", str(exc), 400)

    try:
        collection = get_files_collection()
        total = collection.count_documents({})
        documents = (
            collection.find({}, {"preview": 0})
            .sort("uploaded_at", -1)
            .skip((page - 1) * size)
            .limit(size)
        )
        files = [_serialize_file(document) for document in documents]
    except PyMongoError as exc:
        return error_response("DATABASE_UNAVAILABLE", "MongoDB is not available: %s" % exc, 503)

    return jsonify({"files": files, "total": total, "page": page, "size": size}), 200
