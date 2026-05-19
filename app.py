from flask import Flask
from routes.dashboard import dashboard_bp
from routes.api import api_bp
from routes.pipeline import pipeline_bp

app = Flask(__name__)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(pipeline_bp, url_prefix="/pipeline")

if __name__ == "__main__":
    app.run(debug=True)