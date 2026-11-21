from flask import jsonify

ERROR_CODES = {
    400: "BAD_REQUEST",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}

ERROR_SCHEMA = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message", "status"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "status": {"type": "integer"},
                "detail": {"type": "object"},
            },
        }
    },
}

ERROR_RESPONSE = {
    "description": "Erreur JSON normalisée (BNF4)",
    "content": {"application/json": {"schema": ERROR_SCHEMA}},
}


def error_payload(code, message, status, detail=None):
    error = {"code": code, "message": message, "status": status}
    if detail:
        error["detail"] = detail
    return {"error": error}


def error_response(code, message, status, detail=None):
    return jsonify(error_payload(code, message, status, detail)), status


def code_for_status(status):
    return ERROR_CODES.get(status, "INTERNAL_ERROR")
