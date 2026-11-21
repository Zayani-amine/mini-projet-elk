from flask import Blueprint, jsonify, request
from pymongo.errors import PyMongoError

from app.services.elasticsearch_search import (
    SearchBackendError,
    SearchValidationError,
    build_history_document,
    parse_search_params,
    search_logs,
)
from app.services.search_history import list_searches, record_search

api_v1_search = Blueprint("api_v1_search", __name__, url_prefix="/api/v1")


def _pagination(args):
    try:
        page = int(args.get("page", 1))
        size = int(args.get("size", 10))
    except (TypeError, ValueError):
        raise SearchValidationError("page and size must be integers")
    if page < 1:
        raise SearchValidationError("page must be at least 1")
    if size < 1 or size > 100:
        raise SearchValidationError("size must be between 1 and 100")
    return page, size


@api_v1_search.get("/search")
def search():
    try:
        params = parse_search_params(request.args)
    except SearchValidationError as exc:
        return jsonify(error="invalid_search_params", message=str(exc)), 400

    try:
        result = search_logs(params)
    except SearchBackendError as exc:
        return jsonify(error="elasticsearch_unavailable", message=str(exc)), 503

    document = build_history_document(params, result)
    try:
        history_id = record_search(document)
    except (PyMongoError, RuntimeError) as exc:
        return jsonify(
            error="database_unavailable",
            message="MongoDB is not available: %s" % exc,
        ), 503

    result["history_id"] = history_id
    return jsonify(result), 200


@api_v1_search.get("/history")
def history():
    try:
        page, size = _pagination(request.args)
    except SearchValidationError as exc:
        return jsonify(error="invalid_pagination", message=str(exc)), 400

    query = str(request.args.get("q", "")).strip()[:256]
    try:
        return jsonify(list_searches(page, size, query)), 200
    except (PyMongoError, RuntimeError) as exc:
        return jsonify(
            error="database_unavailable",
            message="MongoDB is not available: %s" % exc,
        ), 503
