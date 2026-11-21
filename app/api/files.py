import csv
import io
import shutil
from datetime import datetime, timezone
from pathlib import Path

from bson.errors import InvalidId
from bson.objectid import ObjectId
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


def _published_name(stored_name, source_file_id):
    if stored_name.lower().endswith(".txt"):
        return source_file_id + ".csv"
    return stored_name


def _publish_to_inbox(stored_name, source_file_id):
    directory = Path(current_app.config["INBOX_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    published_name = _published_name(stored_name, source_file_id)
    temporary = directory / (published_name + ".tmp")
    final = directory / published_name
    if stored_name.lower().endswith(".txt"):
        text = _staging_path(stored_name).read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(text), delimiter="|")
        if not reader.fieldnames:
            raise ValueError("Missing header row in TXT upload")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=reader.fieldnames, delimiter=",")
        writer.writeheader()
        writer.writerows(reader)
        temporary.write_text(output.getvalue(), encoding="utf-8")
    else:
        shutil.copyfile(_staging_path(stored_name), temporary)
    temporary.replace(final)
    return final


def _serialize_file(document):
    data = dict(document)
    data["file_id"] = str(data.pop("_id"))
    for field in ("uploaded_at", "updated_at", "sent_at", "indexed_at"):
        if data.get(field) is not None:
            data[field] = data[field].isoformat()
    data.setdefault("preview", [])
    return data


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
    source_file_id = Path(stored_name).stem
    published_name = _published_name(stored_name, source_file_id)
    staged_path = _staging_path(stored_name)
    staged_path.write_bytes(content)

    collection = get_files_collection()
    document = {
        "original_name": uploaded.filename,
        "stored_name": stored_name,
        "source_file_id": source_file_id,
        "upload_path": "uploads/" + published_name,
        "log_type": result["log_type"],
        "format": result["format"],
        "size_bytes": result["size_bytes"],
        "sha256": result["sha256"],
        "status": "validated",
        "logs_count": result["logs_count"],
        "preview": result["preview"],
        "error_message": None,
        "es_index": None,
        "uploaded_at": now,
        "updated_at": now,
        "sent_at": None,
        "indexed_at": None,
    }

    try:
        inserted = collection.insert_one(document)
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

    try:
        _publish_to_inbox(stored_name, source_file_id)
    except (OSError, ValueError, UnicodeDecodeError, csv.Error) as exc:
        failed_at = _utc_now()
        collection.update_one(
            {"_id": inserted.inserted_id},
            {
                "$set": {
                    "status": "failed",
                    "error_message": "Publish to inbox failed: %s" % exc,
                    "updated_at": failed_at,
                }
            },
        )
        return jsonify(
            error="publish_failed",
            message="The file could not be sent to Logstash: %s" % exc,
        ), 503

    sent_at = _utc_now()
    collection.update_one(
        {"_id": inserted.inserted_id},
        {"$set": {"status": "ingesting", "sent_at": sent_at, "updated_at": sent_at}},
    )

    return jsonify(
        file_id=str(inserted.inserted_id),
        original_name=uploaded.filename,
        stored_name=stored_name,
        source_file_id=source_file_id,
        upload_path="uploads/" + published_name,
        log_type=result["log_type"],
        format=result["format"],
        size_bytes=result["size_bytes"],
        sha256=result["sha256"],
        logs_count=result["logs_count"],
        preview=result["preview"],
        status="ingesting",
        sent_at=sent_at.isoformat(),
        uploaded_at=now.isoformat(),
    ), 201


@api_v1.get("/files/<file_id>")
def get_file(file_id):
    try:
        object_id = ObjectId(file_id)
    except InvalidId:
        return jsonify(
            error="invalid_file_id",
            message="The file_id must be a 24-character hexadecimal ObjectId.",
        ), 400

    try:
        document = get_files_collection().find_one({"_id": object_id})
    except PyMongoError as exc:
        return jsonify(
            error="database_unavailable",
            message="MongoDB is not available: %s" % exc,
        ), 503

    if document is None:
        return jsonify(
            error="file_not_found",
            message="No file found with id %s." % file_id,
        ), 404

    return jsonify(_serialize_file(document)), 200
