// Initialise la base MongoDB du projet (ELK-11 / T05). Exécution : mongosh "<uri>" init_mongo.js
const database = db.getSiblingDB("elk_logs");
const existing = database.getCollectionNames();

// ---- files : métadonnées des fichiers (BF4, BF5)
if (!existing.includes("files")) {
  database.createCollection("files", { validator: { $jsonSchema: {
    "bsonType": "object",
    "required": [
      "original_name",
      "stored_name",
      "log_type",
      "format",
      "size_bytes",
      "sha256",
      "status",
      "logs_count",
      "uploaded_at",
      "updated_at"
    ],
    "properties": {
      "original_name": {
        "bsonType": "string"
      },
      "stored_name": {
        "bsonType": "string"
      },
      "source_file_id": {
        "bsonType": "string"
      },
      "upload_path": {
        "bsonType": "string"
      },
      "log_type": {
        "enum": [
          "capteurs",
          "alertes",
          "maintenance",
          "energie",
          "occupation"
        ]
      },
      "format": {
        "enum": [
          "csv",
          "json",
          "txt"
        ]
      },
      "size_bytes": {
        "bsonType": "number",
        "minimum": 0,
        "maximum": 104857600
      },
      "sha256": {
        "bsonType": "string"
      },
      "status": {
        "enum": [
          "uploaded",
          "validated",
          "rejected",
          "ingesting",
          "indexed",
          "failed"
        ]
      },
      "logs_count": {
        "bsonType": "number",
        "minimum": 0
      },
      "preview": {
        "bsonType": "array",
        "maxItems": 10,
        "items": {
          "bsonType": "string"
        }
      },
      "error_message": {
        "bsonType": [
          "string",
          "null"
        ]
      },
      "es_index": {
        "bsonType": [
          "string",
          "null"
        ]
      },
      "uploaded_at": {
        "bsonType": "date"
      },
      "updated_at": {
        "bsonType": "date"
      },
      "sent_at": {
        "bsonType": [
          "date",
          "null"
        ]
      },
      "indexed_at": {
        "bsonType": [
          "date",
          "null"
        ]
      },
      "indexed_count": {
        "bsonType": [
          "number",
          "null"
        ]
      }
    }
  } } });
}
database.files.createIndex({"uploaded_at": -1}, {});
database.files.createIndex({"status": 1, "uploaded_at": -1}, {});
database.files.createIndex({"log_type": 1}, {});
database.files.createIndex({"source_file_id": 1}, {});
database.files.createIndex({"sha256": 1}, {"unique": true});

// ---- searches : historique des recherches (BF5, BF9)
if (!existing.includes("searches")) {
  database.createCollection("searches", { validator: { $jsonSchema: {
    "bsonType": "object",
    "required": [
      "created_at",
      "query",
      "filters",
      "sort",
      "page",
      "results_count",
      "took_ms",
      "cache_hit"
    ],
    "properties": {
      "created_at": {
        "bsonType": "date"
      },
      "query": {
        "bsonType": "string"
      },
      "filters": {
        "bsonType": "object",
        "properties": {
          "log_types": {
            "bsonType": "array",
            "items": {
              "enum": [
                "capteurs",
                "alertes",
                "maintenance",
                "energie",
                "occupation"
              ]
            }
          },
          "severity": {
            "bsonType": [
              "string",
              "null"
            ]
          },
          "zone": {
            "bsonType": [
              "string",
              "null"
            ]
          },
          "entity_id": {
            "bsonType": [
              "string",
              "null"
            ]
          },
          "date_from": {
            "bsonType": [
              "date",
              "null"
            ]
          },
          "date_to": {
            "bsonType": [
              "date",
              "null"
            ]
          }
        }
      },
      "sort": {
        "bsonType": "string"
      },
      "page": {
        "bsonType": "number",
        "minimum": 1
      },
      "results_count": {
        "bsonType": "number",
        "minimum": 0
      },
      "took_ms": {
        "bsonType": "number",
        "minimum": 0
      },
      "cache_hit": {
        "bsonType": "bool"
      }
    }
  } } });
}
database.searches.createIndex({"created_at": -1}, {});
database.searches.createIndex({"created_at": 1}, {"expireAfterSeconds": 7776000});

// ---- thresholds : seuils d'alerte (US13, BF6)
if (!existing.includes("thresholds")) {
  database.createCollection("thresholds", { validator: { $jsonSchema: {
    "bsonType": "object",
    "required": [
      "measure",
      "zone",
      "operator",
      "critical_value",
      "unit",
      "enabled",
      "updated_at"
    ],
    "properties": {
      "measure": {
        "enum": [
          "temperature",
          "humidity",
          "co2",
          "luminosity",
          "energy"
        ]
      },
      "zone": {
        "bsonType": [
          "string",
          "null"
        ]
      },
      "operator": {
        "enum": [
          "gt",
          "lt"
        ]
      },
      "warning_value": {
        "bsonType": "number"
      },
      "critical_value": {
        "bsonType": "number"
      },
      "unit": {
        "bsonType": "string"
      },
      "enabled": {
        "bsonType": "bool"
      },
      "updated_at": {
        "bsonType": "date"
      }
    }
  } } });
}
database.thresholds.createIndex({"measure": 1, "zone": 1}, {"unique": true});

print("Collections et index prêts : " + database.getCollectionNames().join(", "));
