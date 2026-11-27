from apiflask import APIBlueprint
from flask import jsonify, request
from pymongo.errors import PyMongoError

from app.api.errors import ERROR_RESPONSE, error_response
from app.api.schemas import HistoryQuery, SearchQuery, SuggestQuery
from app.services.elasticsearch_search import (
    SearchBackendError,
    SearchValidationError,
    build_history_document,
    parse_search_params,
    parse_suggest_params,
    search_logs,
    suggest_values,
)
from app.services.search_history import list_searches, record_search
from app.utils.cache import cached_value, make_key

api_v1_search = APIBlueprint(
    "api_v1_search",
    __name__,
    url_prefix="/api/v1",
    tag="Recherche",
)

SUCCESS_JSON = {
    "description": "Réponse JSON",
    "content": {"application/json": {"schema": {"type": "object"}}},
}


def _pagination(args):
    try:
        page = int(args.get("page", 1))
        size = int(args.get("size", 10))
    except (TypeError, ValueError) as exc:
        raise SearchValidationError("page and size must be integers") from exc
    if page < 1:
        raise SearchValidationError("page must be at least 1")
    if size < 1 or size > 100:
        raise SearchValidationError("size must be between 1 and 100")
    return page, size


@api_v1_search.get("/search")
@api_v1_search.input(SearchQuery, location="query", validation=False)
@api_v1_search.doc(
    summary="Rechercher des logs",
    tags=["Recherche"],
    description="Interroge sb-logs-*,logs-* et enregistre la recherche dans MongoDB.",
    responses={
        200: SUCCESS_JSON,
        400: ERROR_RESPONSE,
        503: ERROR_RESPONSE,
    },
)
def search(query_data):
    try:
        params = parse_search_params(request.args)
    except SearchValidationError as exc:
        return error_response("INVALID_SEARCH_PARAMS", str(exc), 400)

    try:
        result = search_logs(params)
    except SearchBackendError as exc:
        return error_response("ELASTICSEARCH_UNAVAILABLE", str(exc), 503)

    document = build_history_document(params, result)
    try:
        history_id = record_search(document)
    except (PyMongoError, RuntimeError) as exc:
        return error_response(
            "DATABASE_UNAVAILABLE",
            "MongoDB is not available: %s" % exc,
            503,
        )

    result["history_id"] = history_id
    return jsonify(result), 200


@api_v1_search.get("/suggest")
@api_v1_search.input(SuggestQuery, location="query", validation=False)
@api_v1_search.doc(
    summary="Proposer des valeurs indexées",
    tags=["Recherche"],
    description="Retourne des valeurs réelles d'Elasticsearch pour l'autocomplétion, sans écrire dans l'historique.",
    responses={
        200: SUCCESS_JSON,
        400: ERROR_RESPONSE,
        503: ERROR_RESPONSE,
    },
)
def suggest(query_data):
    try:
        params = parse_suggest_params(request.args)
    except SearchValidationError as exc:
        return error_response("INVALID_SUGGEST_PARAMS", str(exc), 400)

    if not params["q"]:
        return jsonify({"suggestions": [], "took_ms": 0, "cache_hit": False}), 200

    key = make_key(
        "elk:suggest:v1",
        {
            "q": params["q"].lower(),
            "log_type": params["log_type"],
            "source_file_id": params["source_file_id"],
            "severity": params["severity"],
            "zone": params["zone"],
            "entity_id": params["entity_id"],
            "date_from": params["date_from"],
            "date_to": params["date_to"],
            "size": params["size"],
        },
    )

    try:
        payload, cache_hit = cached_value(key, 30, lambda: suggest_values(params))
    except SearchBackendError as exc:
        return error_response("ELASTICSEARCH_UNAVAILABLE", str(exc), 503)

    payload["cache_hit"] = cache_hit
    return jsonify(payload), 200


@api_v1_search.get("/history")
@api_v1_search.input(HistoryQuery, location="query", validation=False)
@api_v1_search.doc(
    summary="Lire l'historique des recherches",
    tags=["Recherche"],
    description="Retourne les recherches enregistrées dans la collection MongoDB searches.",
    responses={
        200: SUCCESS_JSON,
        400: ERROR_RESPONSE,
        503: ERROR_RESPONSE,
    },
)
def history(query_data):
    try:
        page, size = _pagination(request.args)
    except SearchValidationError as exc:
        return error_response("INVALID_PAGINATION", str(exc), 400)

    query = str(request.args.get("q", "")).strip()[:256]
    try:
        return jsonify(list_searches(page, size, query)), 200
    except (PyMongoError, RuntimeError) as exc:
        return error_response(
            "DATABASE_UNAVAILABLE",
            "MongoDB is not available: %s" % exc,
            503,
        )
