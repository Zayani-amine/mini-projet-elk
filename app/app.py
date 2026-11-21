import os

from apiflask import APIFlask
from werkzeug.exceptions import RequestEntityTooLarge

from app.api.errors import (
    ERROR_RESPONSE,
    ERROR_SCHEMA,
    code_for_status,
    error_payload,
    error_response,
)
from app.api.files import api_v1
from app.api.search import api_v1_search

JSON_RESPONSE = {
    "description": "Réponse JSON",
    "content": {"application/json": {"schema": {"type": "object"}}},
}
SWAGGER_UPLOAD_ACCEPT = """
() => {
  const apply = () => {
    document.querySelectorAll('input[type="file"]').forEach((input) => {
      input.setAttribute('accept', '.csv,.json,.txt,text/csv,application/json,text/plain');
    });
  };
  apply();
  new MutationObserver(apply).observe(document.body, {childList: true, subtree: true});
}
"""


def create_app():
    app = APIFlask(
        __name__,
        title="Smart Building IoT API",
        version="1.0.0",
    )
    app.config["DESCRIPTION"] = (
        "API d'upload, de suivi, de recherche et d'historique du projet ELK."
    )
    app.config["VALIDATION_ERROR_STATUS_CODE"] = 400
    app.config["HTTP_ERROR_SCHEMA"] = ERROR_SCHEMA
    app.config["VALIDATION_ERROR_SCHEMA"] = ERROR_SCHEMA
    app.config["SWAGGER_UI_CONFIG"] = {"onComplete": SWAGGER_UPLOAD_ACCEPT}
    app.tags = [
        {"name": "Système", "description": "Contrôles de disponibilité du service"},
        {"name": "Fichiers", "description": "Upload, suivi et aperçu des fichiers"},
        {"name": "Recherche", "description": "Recherche Elasticsearch et historique MongoDB"},
    ]

    max_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", "104857600"))
    app.config["MAX_CONTENT_LENGTH"] = max_bytes
    app.config["MAX_UPLOAD_BYTES"] = max_bytes
    app.config["STAGING_DIR"] = os.environ.get("STAGING_DIR", "/app/data/staging")
    app.config["INBOX_DIR"] = os.environ.get("INBOX_DIR", "/app/data/inbox/uploads")

    app.register_blueprint(api_v1)
    app.register_blueprint(api_v1_search)

    @app.error_processor
    def api_error_processor(error):
        return (
            error_payload(
                code_for_status(error.status_code),
                error.message,
                error.status_code,
                error.detail,
            ),
            error.status_code,
            error.headers,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return error_response(
            "PAYLOAD_TOO_LARGE",
            "Uploaded file is too large (limit: %d bytes)." % max_bytes,
            413,
        )

    if os.environ.get("ENABLE_STATUS_POLLER", "1") == "1":
        from app.services.ingest_status import start_status_poller

        start_status_poller(app)

    @app.get("/")
    @app.doc(summary="Page d'accueil", tags=["Système"])
    def index():
        return "Mini-Projet ELK - Smart Building IoT"

    @app.get("/health")
    @app.doc(
        summary="État de santé du service",
        tags=["Système"],
        responses={200: JSON_RESPONSE},
    )
    def health():
        return {"status": "healthy", "service": "webapp"}

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000)
