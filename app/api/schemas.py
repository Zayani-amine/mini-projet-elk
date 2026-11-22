from apiflask import Schema, fields
from apiflask.validators import OneOf, Range

from app.utils.upload_validation import LOG_TYPES

LOG_TYPE_VALUES = sorted(LOG_TYPES)


class UploadInput(Schema):
    file = fields.File(
        required=True,
        metadata={"description": "Fichier .csv, .json ou .txt uniquement (100 Mo maximum)"},
    )


class SearchQuery(Schema):
    q = fields.String(
        metadata={
            "description": "Recherche plein texte tolérant aux fautes (ex: temperatur trouve temperature)",
            "example": "temperatur",
        }
    )
    log_type = fields.String(
        validate=OneOf(LOG_TYPE_VALUES),
        metadata={"description": "Type de log"},
    )
    date_from = fields.String(
        data_key="from",
        metadata={
            "format": "date-time",
            "description": "Date ISO-8601 minimale, inclusive",
        },
    )
    date_to = fields.String(
        data_key="to",
        metadata={
            "format": "date-time",
            "description": "Date ISO-8601 maximale, inclusive",
        },
    )
    source_file_id = fields.String(metadata={"description": "Identifiant du fichier source"})
    severity = fields.String(metadata={"description": "Sévérité d'une alerte"})
    zone = fields.String(metadata={"description": "Zone du bâtiment"})
    entity_id = fields.String(metadata={"description": "Alias de sensor_id, meter_id ou room_id"})
    page = fields.Integer(load_default=1, validate=Range(min=1))
    size = fields.Integer(load_default=20, validate=Range(min=1, max=100))
    sort = fields.String(
        load_default="recent",
        validate=OneOf(["recent", "oldest"]),
        metadata={"description": "Tri par @timestamp"},
    )


class HistoryQuery(Schema):
    q = fields.String(metadata={"description": "Filtre sur la requête enregistrée"})
    page = fields.Integer(load_default=1, validate=Range(min=1))
    size = fields.Integer(load_default=10, validate=Range(min=1, max=100))
