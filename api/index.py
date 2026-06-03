"""
MRSI Platform - Vercel Serverless Entry Point

This module adapts the Flask application for Vercel's serverless environment.
It handles all web routes and serves the dashboard interface.

IMPORTANT: For Vercel deployment, environment variables must be configured
in the Vercel Dashboard (Project Settings → Environment Variables).
The .env file is NOT deployed to Vercel.
"""

import json
import os
import sys
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, send_from_directory, jsonify
from dotenv import load_dotenv

# Load environment variables (works for local development with .env file)
load_dotenv()

# Import route blueprints
sys.path.insert(0, str(Path(__file__).parent.parent / "routes"))

def check_environment():
    """Check if required environment variables are configured."""
    missing_vars = []
    
    # Check for required variables
    if not os.getenv("GEMINI_API_KEY"):
        missing_vars.append("GEMINI_API_KEY")
    
    if missing_vars:
        logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.warning("For Vercel deployment, add these in Project Settings → Environment Variables")
        logger.warning("See VERCEL_ENV_SETUP.md for detailed instructions")
        return False
    
    return True

def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="../static",
        template_folder="../templates"
    )
    
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-key"),
        DEBUG=os.getenv("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    )
    
    # Check environment on startup
    env_ok = check_environment()
    if not env_ok:
        logger.error("Some required environment variables are missing. Pipeline features may not work.")
    
    # Register blueprints
    from routes.dashboard import dashboard_bp
    from routes.api import api_bp
    from routes.pipeline import pipeline_bp
    from routes.tlp_insights import tlp_insights_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(pipeline_bp, url_prefix="/pipeline")
    app.register_blueprint(tlp_insights_bp, url_prefix="/v2")
    
    # Health check endpoint
    @app.get("/healthz")
    def healthcheck():
        env_ok = check_environment()
        return jsonify({
            "status": "ok" if env_ok else "warning",
            "environment_configured": env_ok
        }), 200
    
    # Environment check endpoint
    @app.get("/api/env-check")
    def env_check():
        """Check environment variable configuration."""
        return jsonify({
            "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
            "storage_backend": os.getenv("STORAGE_BACKEND", "local"),
            "debug_mode": app.config.get("DEBUG", False),
            "vercel_env": os.getenv("VERCEL", "false").lower() == "1"
        })
    
    # Serve static files
    @app.route("/static/<path:filename>")
    def serve_static(filename):
        return send_from_directory(app.static_folder, filename)
    
    # Fallback route
    @app.route("/<path:path>")
    def catch_all(path):
        return render_template("dashboard.html", active_page="dashboard", 
                             active_page_title="Dashboard", metrics={
                                 "topics": 0, "insights": 0, 
                                 "tlp_docs": 0, "social_pieces": 0
                             })
    
    return app

# Create the app instance
app = create_app()

# Vercel serverless handler
def handler(request):
    """Vercel serverless function handler."""
    return app(request.environ, lambda *args: None)
