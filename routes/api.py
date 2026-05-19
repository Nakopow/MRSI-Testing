from flask import Blueprint, jsonify
from main import parse_digest_sections, load_tlp_payloads

api_bp = Blueprint("api", __name__)

@api_bp.route("/status")
def status():
    sections = parse_digest_sections("output.txt")
    tlp = load_tlp_payloads()
    return jsonify({
        "topics": len(sections),
        "tlp_topics": len(tlp),
        "total_pieces": sum(len(p.get("pieces", [])) for p in tlp.values())
    })
