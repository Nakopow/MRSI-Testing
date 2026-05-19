from flask import Blueprint, jsonify
import threading
from main import main as run_pipeline

pipeline_bp = Blueprint("pipeline", __name__)

@pipeline_bp.route("/run", methods=["POST"])
def run():
    thread = threading.Thread(target=run_pipeline)
    thread.start()
    return jsonify({"status": "started"})
