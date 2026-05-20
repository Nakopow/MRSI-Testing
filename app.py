from flask import Flask
from routes.dashboard import dashboard_bp
from routes.api import api_bp
from routes.pipeline import pipeline_bp
from routes.tlp_insights import tlp_insights_bp   # ← new

app = Flask(__name__)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(pipeline_bp, url_prefix="/pipeline")
app.register_blueprint(tlp_insights_bp, url_prefix="/v2")  # ← new

if __name__ == "__main__":
    app.run(debug=True)