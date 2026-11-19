from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.services.mongo import get_files_collection
from app.utils.upload_validation import UploadValidationError, validate_upload

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


def _utc_now():
    return datetime.now(timezone.utc)


def _staging_path(stored_name):
    directory = Path(current_app.config["STAGING_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    return directory / stored_name


@api_v1.post("/upload")
def upload_file():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify(
            error="missing_file",
            message="A multipart field named 'file' is required.",
        ), 400

    content = uploaded.read()
    max_bytes = current_app.config["MAX_UPLOAD_BYTES"]
    try:
        result = validate_upload(uploaded.filename, content, max_bytes)
    except UploadValidationError as exc:
        return jsonify(error="invalid_upload", message=str(exc)), exc.status_code

    now = _utc_now()
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    stored_name = "%s_%s.%s" % (stamp, result["sha256"][:12], result["format"])
    staged_path = _staging_path(stored_name)
    staged_path.write_bytes(content)

    document = {
        "original_name": uploaded.filename,
        "stored_name": stored_name,
        "log_type": result["log_type"],
        "format": result["format"],
        "size_bytes": result["size_bytes"],
        "sha256": result["sha256"],
        "status": "validated",
        "logs_count": result["logs_count"],
        "error_message": None,
        "es_index": None,
        "uploaded_at": now,
        "updated_at": now,
        "indexed_at": None,
    }

    try:
        inserted = get_files_collection().insert_one(document)
    except DuplicateKeyError:
        staged_path.unlink(missing_ok=True)
        return jsonify(
            error="duplicate_file",
            message="A file with this SHA-256 was already uploaded.",
        ), 409
    except PyMongoError as exc:
        staged_path.unlink(missing_ok=True)
        return jsonify(
            error="database_unavailable",
            message="MongoDB is not available: %s" % exc,
        ), 503

    return jsonify(
        file_id=str(inserted.inserted_id),
        original_name=uploaded.filename,
        stored_name=stored_name,
        log_type=result["log_type"],
        format=result["format"],
        size_bytes=result["size_bytes"],
        sha256=result["sha256"],
        logs_count=result["logs_count"],
        status="validated",
        uploaded_at=now.isoformat(),
    ), 201
