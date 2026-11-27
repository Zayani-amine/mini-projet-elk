import os

from apiflask import APIFlask
from flask import render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

from app.api.dashboard import api_v1_dashboard
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
SWAGGER_UI_ENHANCEMENTS = """
() => {
  const allowedExtensions = ['csv', 'json', 'txt'];

  const showError = (input, message) => {
    let error = input.parentElement.querySelector('.elk-file-error');
    if (!error) {
      error = document.createElement('div');
      error.className = 'elk-file-error';
      error.style.cssText = 'color:#b00020;font-size:12px;margin-top:6px;font-weight:600;';
      input.parentElement.appendChild(error);
    }
    error.textContent = message;
  };

  const clearError = (input) => {
    const error = input.parentElement.querySelector('.elk-file-error');
    if (error) error.remove();
  };

  const pickFile = async (input, label) => {
    if (!window.showOpenFilePicker) {
      input.click();
      return;
    }
    try {
      const handles = await window.showOpenFilePicker({
        types: [{
          description: 'Logs .csv .json .txt',
          accept: {
            'text/csv': ['.csv'],
            'application/json': ['.json'],
            'text/plain': ['.txt']
          }
        }],
        excludeAcceptAllOption: true,
        multiple: false
      });
      const file = await handles[0].getFile();
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      label.textContent = file.name;
      clearError(input);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    } catch (error) {
      if (error && error.name === 'AbortError') return;
      showError(input, 'Sélection impossible dans ce navigateur.');
    }
  };

  const enhanceFileInput = (input) => {
    if (input.dataset.elkEnhanced === '1') return;
    input.dataset.elkEnhanced = '1';
    input.setAttribute('accept', '.csv,.json,.txt');
    input.style.display = 'none';

    const name = document.createElement('span');
    name.className = 'elk-file-name';
    name.style.cssText = 'display:inline-block;margin-left:8px;font-size:13px;';
    name.textContent = 'Aucun fichier sélectionné';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'elk-upload-button';
    button.textContent = 'Choisir un fichier .csv/.json/.txt';
    button.style.cssText = 'padding:7px 12px;border:1px solid #4990e2;border-radius:4px;background:#e8f2ff;color:#174a7e;cursor:pointer;font-weight:600;';
    button.addEventListener('click', () => pickFile(input, name));

    const hint = document.createElement('div');
    hint.className = 'elk-file-hint';
    hint.style.cssText = 'color:#666;font-size:12px;margin-top:4px;';
    hint.textContent = 'Seuls .csv, .json et .txt sont acceptés.';

    input.parentElement.insertBefore(button, input);
    input.parentElement.insertBefore(name, input.nextSibling);
    input.parentElement.appendChild(hint);

    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      if (!file) {
        name.textContent = 'Aucun fichier sélectionné';
        return;
      }
      const extension = file.name.split('.').pop().toLowerCase();
      if (allowedExtensions.indexOf(extension) === -1) {
        showError(input, 'Formats autorisés : .csv, .json, .txt');
        input.value = '';
        name.textContent = 'Aucun fichier sélectionné';
        return;
      }
      clearError(input);
      name.textContent = file.name;
    });
  };

  const toLocalValue = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (number) => String(number).padStart(2, '0');
    return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()) + 'T' + pad(date.getHours()) + ':' + pad(date.getMinutes());
  };

  const enhanceDateInput = (input) => {
    if (input.dataset.elkDateEnhanced === '1') return;
    const row = input.closest('.parameter') || input.parentElement;
    if (!row) return;
    const nameElement = row.querySelector('.parameter-name');
    const name = nameElement ? nameElement.textContent.trim() : '';
    if (name !== 'from' && name !== 'to') return;
    input.dataset.elkDateEnhanced = '1';
    input.style.display = 'none';

    const calendar = document.createElement('input');
    calendar.type = 'datetime-local';
    calendar.className = 'elk-datetime-input';
    calendar.style.cssText = 'padding:6px;border:1px solid #ccc;border-radius:4px;';
    calendar.value = toLocalValue(input.value);
    input.parentElement.insertBefore(calendar, input.nextSibling);

    calendar.addEventListener('change', () => {
      const iso = calendar.value ? new Date(calendar.value).toISOString() : '';
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(input, iso);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    });
  };

  const addBanner = () => {
    const info = document.querySelector('.swagger-ui .info');
    if (!info || document.querySelector('.elk-docs-banner')) return;
    const banner = document.createElement('div');
    banner.className = 'elk-docs-banner';
    banner.style.cssText = 'margin-bottom:14px;padding:10px 12px;border-left:4px solid #2e7d32;background:#e8f5e9;color:#1b5e20;font-weight:600;';
    banner.textContent = 'ELK API v1.1.0 : recherche floue, dates calendrier, upload .csv/.json/.txt sans option « Tous les fichiers » sous Chrome/Edge.';
    info.prepend(banner);
  };

  const apply = () => {
    addBanner();
    document.querySelectorAll('input[type="file"]').forEach(enhanceFileInput);
    document.querySelectorAll('input[type="text"]').forEach(enhanceDateInput);
  };

  apply();
  new MutationObserver(apply).observe(document.body, { childList: true, subtree: true });
}
"""


def create_app():
    app = APIFlask(
        __name__,
        title="Smart Building IoT API",
        version="1.1.0",
    )
    app.config["DESCRIPTION"] = (
        "API d'upload, de suivi, de recherche et d'historique du projet ELK."
    )
    app.config["VALIDATION_ERROR_STATUS_CODE"] = 400
    app.config["HTTP_ERROR_SCHEMA"] = ERROR_SCHEMA
    app.config["VALIDATION_ERROR_SCHEMA"] = ERROR_SCHEMA
    app.config["SWAGGER_UI_CONFIG"] = {"onComplete": SWAGGER_UI_ENHANCEMENTS}
    app.tags = [
        {"name": "Système", "description": "Contrôles de disponibilité du service"},
        {"name": "Fichiers", "description": "Upload, suivi et aperçu des fichiers"},
        {"name": "Recherche", "description": "Recherche Elasticsearch et historique MongoDB"},
        {"name": "Tableau de bord", "description": "KPI, export et suivi des fichiers"},
        {"name": "Interface web", "description": "Pages Bootstrap du tableau de bord"},
    ]

    max_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", "104857600"))
    app.config["MAX_CONTENT_LENGTH"] = max_bytes
    app.config["MAX_UPLOAD_BYTES"] = max_bytes
    app.config["STAGING_DIR"] = os.environ.get("STAGING_DIR", "/app/data/staging")
    app.config["INBOX_DIR"] = os.environ.get("INBOX_DIR", "/app/data/inbox/uploads")

    @app.context_processor
    def inject_site_settings():
        return {
            "public_base_url": os.environ.get("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/"),
            "kibana_url": os.environ.get("KIBANA_URL", "http://localhost:5601").rstrip("/"),
        }

    app.register_blueprint(api_v1)
    app.register_blueprint(api_v1_search)
    app.register_blueprint(api_v1_dashboard)

    @app.after_request
    def disable_docs_cache(response):
        if request.path in ("/docs", "/openapi.json"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

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

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return error_response("NOT_FOUND", "Resource not found", 404)
        return render_template("404.html"), 404

    @app.get("/")
    @app.doc(summary="Page d'accueil du tableau de bord", tags=["Interface web"])
    def index():
        return render_template("index.html")

    @app.get("/upload")
    @app.doc(summary="Page de dépôt de fichiers", tags=["Interface web"])
    def upload_page():
        return render_template("upload.html")

    @app.get("/search")
    @app.doc(summary="Page de recherche", tags=["Interface web"])
    def search_page():
        return render_template("search.html")

    @app.get("/results")
    @app.doc(summary="Page des résultats de recherche", tags=["Interface web"])
    def results_page():
        return render_template("results.html")

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
