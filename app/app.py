from flask import Flask, jsonify


def create_app():
    app = Flask(__name__)

    @app.get("/")
    def index():
        return "Mini-Projet ELK - Smart Building IoT"

    @app.get("/health")
    def health():
        return jsonify(status="healthy", service="webapp")

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000)
