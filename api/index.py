"""
MRSI Platform - Vercel Serverless Entry Point

This module adapts the Flask application for Vercel's serverless environment.
It handles all web routes and serves the dashboard interface.
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, send_from_directory, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import route blueprints
sys.path.insert(0, str(Path(__file__).parent.parent / "routes"))

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
        return jsonify({"status": "ok"}), 200
    
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