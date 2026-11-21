import os

from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from app.api.files import api_v1
from app.api.search import api_v1_search


def create_app():
    app = Flask(__name__)

    max_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", "104857600"))
    app.config["MAX_CONTENT_LENGTH"] = max_bytes
    app.config["MAX_UPLOAD_BYTES"] = max_bytes
    app.config["STAGING_DIR"] = os.environ.get("STAGING_DIR", "/app/data/staging")
    app.config["INBOX_DIR"] = os.environ.get("INBOX_DIR", "/app/data/inbox/uploads")

    app.register_blueprint(api_v1)
    app.register_blueprint(api_v1_search)

    if os.environ.get("ENABLE_STATUS_POLLER", "1") == "1":
        from app.services.ingest_status import start_status_poller

        start_status_poller(app)

    @app.errorhandler(RequestEntityTooLarge)
    def request_too_large(_error):
        return jsonify(
            error="file_too_large",
            message="Uploaded file is too large.",
        ), 413

    @app.get("/")
    def index():
        return "Mini-Projet ELK - Smart Building IoT"

    @app.get("/health")
    def health():
        return jsonify(status="healthy", service="webapp")

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000)
