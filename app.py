import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from routes.api import api_bp
from routes.dashboard import dashboard_bp
from routes.pipeline import pipeline_bp
from routes.tlp_insights import tlp_insights_bp

load_dotenv(Path(__file__).resolve().parent / ".env")


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(pipeline_bp, url_prefix="/pipeline")
    app.register_blueprint(tlp_insights_bp, url_prefix="/v2")

    @app.get("/healthz")
    def healthcheck():
        return {"status": "ok"}, 200

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"},
    )
