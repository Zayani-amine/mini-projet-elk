import csv
import hashlib
import io
import json
from datetime import datetime
from pathlib import Path

ALLOWED_EXTENSIONS = {"json", "csv", "txt"}
LOG_TYPES = {"capteurs", "alertes", "maintenance", "energie", "occupation"}
PREVIEW_LIMIT = 10
REQUIRED_FIELDS = {
    "capteurs": ("sensor_id", "zone", "measure", "value", "unit"),
    "alertes": ("alert_id", "sensor_id", "severity", "rule", "threshold"),
    "maintenance": ("equipment_id", "equipment_type", "wear_level", "predicted_failure"),
    "energie": ("meter_id", "energy_type", "quantity", "unit"),
    "occupation": ("room_id", "present_count", "capacity", "occupancy_rate"),
}


class UploadValidationError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _preview_lines(text):
    return [line.strip() for line in text.splitlines() if line.strip()][:PREVIEW_LIMIT]


def _records_from_json(text):
    records = []
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise UploadValidationError(
                "Invalid JSON on line %d: %s" % (number, exc.msg)
            ) from exc
        if not isinstance(value, dict):
            raise UploadValidationError("Line %d must be a JSON object" % number)
        records.append(value)
    return records


def _records_from_delimited(text, delimiter):
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise UploadValidationError("Missing header row")
    return [dict(row) for row in reader]


def _detect_log_type(records, filename):
    declared = str(records[0].get("log_type", "")).strip().lower()
    if declared in LOG_TYPES:
        return declared

    name = Path(filename).name.lower()
    for candidate in LOG_TYPES:
        if name.startswith(candidate):
            return candidate

    raise UploadValidationError("Unknown or missing log_type")


def _validate_records(records, log_type):
    required = REQUIRED_FIELDS[log_type]
    for number, record in enumerate(records, start=1):
        declared = str(record.get("log_type", "")).strip().lower()
        if declared and declared != log_type:
            raise UploadValidationError(
                "Line %d declares log_type '%s', expected '%s'"
                % (number, declared, log_type)
            )
        for field in required:
            if field not in record or record[field] in (None, ""):
                raise UploadValidationError(
                    "Line %d is missing required field '%s'" % (number, field)
                )
        timestamp = record.get("@timestamp")
        if not timestamp:
            raise UploadValidationError("Line %d is missing @timestamp" % number)
        try:
            datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError as exc:
            raise UploadValidationError(
                "Line %d has an invalid @timestamp" % number
            ) from exc


def validate_upload(filename, content, max_bytes):
    if not content:
        raise UploadValidationError("Uploaded file is empty")
    if len(content) > max_bytes:
        raise UploadValidationError("Uploaded file is too large", 413)

    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in ALLOWED_EXTENSIONS:
        raise UploadValidationError(
            "Unsupported file format '%s'; allowed: .csv, .json, .txt" % extension,
            415,
        )

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadValidationError("Uploaded file is not valid UTF-8") from exc

    if extension == "json":
        records = _records_from_json(text)
    elif extension == "csv":
        records = _records_from_delimited(text, ",")
    else:
        records = _records_from_delimited(text, "|")

    if not records:
        raise UploadValidationError("Uploaded file contains no log records")

    log_type = _detect_log_type(records, filename)
    _validate_records(records, log_type)

    return {
        "format": extension,
        "log_type": log_type,
        "logs_count": len(records),
        "preview": _preview_lines(text),
        "records": records,
        "sha256": hashlib.sha256(content).hexdigest(),
        "size_bytes": len(content),
    }
