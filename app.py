import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from routes.api import api_bp
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.pipeline import pipeline_bp
from routes.tlp_insights import tlp_insights_bp

load_dotenv(Path(__file__).resolve().parent / ".env")


def create_app() -> Flask:
    app = Flask(__name__)

    app.secret_key = os.environ.get("SECRET_KEY") or os.urandom(24)
    app.permanent_session_lifetime = timedelta(days=7)

    # SQLite for local dev; set DATABASE_URL (Supabase / any PostgreSQL) for prod
    db_url = os.environ.get("DATABASE_URL", "sqlite:///users.db")
    # Fix legacy postgres:// scheme (Heroku / some Supabase exports)
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # On Vercel (serverless) disable persistent connection pools — each invocation
    # is short-lived and a pool would exhaust Supabase's connection limit fast.
    is_postgres = db_url.startswith("postgresql")
    if is_postgres:
        from sqlalchemy.pool import NullPool
        engine_opts: dict = {"poolclass": NullPool}
        # Supabase requires SSL; add it if the URL doesn't already specify it
        if "sslmode" not in db_url:
            engine_opts["connect_args"] = {"sslmode": "require"}
        if os.environ.get("VERCEL"):
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_opts
        else:
            # Local / Railway — keep a small pool but still enforce SSL
            engine_opts.pop("poolclass", None)
            app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_opts

    # Init DB
    from models import db
    db.init_app(app)
    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)

    # Init Google OAuth (no-op if authlib not installed or creds not set)
    try:
        from routes.auth import oauth as _oauth
        if _oauth is not None:
            _oauth.init_app(app)
    except Exception:
        pass

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(pipeline_bp, url_prefix="/pipeline")
    app.register_blueprint(tlp_insights_bp, url_prefix="/v2")

    @app.get("/healthz")
    def healthcheck():
        return {"status": "ok"}, 200

    # Start background scheduler (skipped automatically on Vercel)
    from src.scheduler import init_scheduler
    init_scheduler()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"},
    )
