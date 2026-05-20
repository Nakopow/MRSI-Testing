"""
routes/tlp_insights.py

Blueprint for the enhanced TLP and Insights pages.
- TLPs: rendered on-page with social-media customization (pick which platforms to include).
- Insights: rendered on-page with full briefing text, tabs per topic.
- Both support daily auto-generation via a /generate endpoint.

Attach to app.py with:
    from routes.tlp_insights import tlp_insights_bp
    app.register_blueprint(tlp_insights_bp, url_prefix="/v2")
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, render_template, request

tlp_insights_bp = Blueprint("tlp_insights", __name__)

TOPIC_LABELS: dict[str, str] = {
    "ai": "Artificial Intelligence",
    "cybersecurity": "Cybersecurity",
    "web3": "Web3 / Blockchain",
}

PLATFORM_ORDER = ["LinkedIn", "YouTube / Video Script", "Instagram Carousel", "Facebook", "TikTok"]

PLATFORM_META: dict[str, dict] = {
    "LinkedIn": {"icon": "ti-brand-linkedin", "color": "#0A66C2", "bg": "#E8F0FE", "slug": "linkedin"},
    "YouTube / Video Script": {"icon": "ti-brand-youtube", "color": "#FF0000", "bg": "#FFE8E8", "slug": "youtube"},
    "Instagram Carousel": {"icon": "ti-brand-instagram", "color": "#E1306C", "bg": "#FDEEF5", "slug": "instagram"},
    "Facebook": {"icon": "ti-brand-facebook", "color": "#1877F2", "bg": "#E7F0FD", "slug": "facebook"},
    "TikTok": {"icon": "ti-brand-tiktok", "color": "#010101", "bg": "#F0F0F0", "slug": "tiktok"},
}

TOPIC_TAG: dict[str, str] = {
    "ai": "tag-ai",
    "cybersecurity": "tag-cyber",
    "web3": "tag-web3",
}


def _load_tl_outputs() -> dict[str, Any]:
    """Load tl_output_*.json files from the project root."""
    result: dict[str, Any] = {}
    for key in TOPIC_LABELS:
        path = Path(f"tl_output_{key}.json")
        if not path.exists() and key == "cybersecurity":
            path = Path("tl_output_cybersecurity.json")
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    result[key] = json.load(f)
            except Exception:
                pass
    return result


def _load_insight_texts() -> dict[str, list[dict]]:
    """
    Load plain-text insight content from output.txt (parse_digest_sections)
    falling back to listing docx filenames with metadata.
    Returns dict keyed by topic_key.
    """
    insight_map: dict[str, list[dict]] = {k: [] for k in TOPIC_LABELS}

    try:
        from main import parse_digest_sections  # type: ignore

        sections = parse_digest_sections("output.txt")
        for key, section in sections.items():
            if key in insight_map:
                insight_map[key].append(
                    {
                        "date": datetime.now().strftime("%B %d, %Y"),
                        "title": section.get("title") or TOPIC_LABELS.get(key, key),
                        "briefing_line": section.get("briefing_line", ""),
                        "summary": section.get("summary", []),
                        "questions": section.get("questions", []),
                        "sources": section.get("sources", []),
                        "source": "output.txt",
                    }
                )
    except Exception:
        pass

    insight_dir = Path("insights")
    if insight_dir.exists():
        for p in sorted(insight_dir.glob("*.docx"), reverse=True):
            name = p.stem
            parts = name.split("_")
            topic_hint = parts[-1].lower() if parts else ""
            matched_key = None
            for k in TOPIC_LABELS:
                if k in topic_hint or topic_hint in k:
                    matched_key = k
                    break
            if matched_key is None:
                if "cyber" in topic_hint:
                    matched_key = "cybersecurity"
                elif "web" in topic_hint or "3" in topic_hint:
                    matched_key = "web3"
                else:
                    matched_key = "ai"

            mtime = datetime.fromtimestamp(p.stat().st_mtime)
            existing_dates = {e.get("date") for e in insight_map[matched_key]}
            date_str = mtime.strftime("%B %d, %Y")
            if date_str not in existing_dates:
                insight_map[matched_key].append(
                    {
                        "date": date_str,
                        "title": p.name,
                        "briefing_line": f"Insight document from {date_str}",
                        "summary": [],
                        "questions": [],
                        "sources": [],
                        "source": "docx",
                        "filename": p.name,
                    }
                )

    return insight_map


def _generation_status() -> dict:
    """Return a simple status dict for the last generation run."""
    status_file = Path(".generation_status.json")
    if status_file.exists():
        try:
            with open(status_file) as f:
                return json.load(f)
        except Exception:
            pass
    return {"running": False, "last_run": None, "message": "Never run"}


def _set_generation_status(running: bool, message: str) -> None:
    status_file = Path(".generation_status.json")
    data = {
        "running": running,
        "last_run": datetime.now().isoformat() if not running else _generation_status().get("last_run"),
        "message": message,
    }
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _run_generation_background(platforms: list[str], topics: list[str], include_tlp: bool = True) -> None:
    """
    Called in a background thread. Runs the main pipeline for insights and,
    optionally, the TLP pipeline.
    """
    try:
        _set_generation_status(True, "Running insight pipeline...")

        try:
            import main as mrsi_main  # type: ignore

            mrsi_main.main()
        except Exception as e:
            _set_generation_status(False, f"Insight pipeline error: {e}")
            return

        if not include_tlp:
            _set_generation_status(False, f"Daily Insights ready - {datetime.now().strftime('%b %d, %Y %I:%M %p')}")
            return

        _set_generation_status(True, "Running TLP pipeline...")

        try:
            import tl_summarizer as tlsum  # type: ignore

            tlsum.main()
        except Exception as e:
            _set_generation_status(False, f"TLP pipeline error: {e}")
            return

        if platforms:
            for key in topics:
                out_path = Path(f"tl_output_{key}.json")
                if out_path.exists():
                    with open(out_path, encoding="utf-8") as f:
                        data = json.load(f)
                    data["pieces"] = [
                        p
                        for p in data.get("pieces", [])
                        if any(pl.lower() in p.get("platform", "").lower() for pl in platforms)
                    ]
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

        _set_generation_status(False, f"TLPs ready - {datetime.now().strftime('%b %d, %Y %I:%M %p')}")
    except Exception as e:
        _set_generation_status(False, f"Unexpected error: {e}")


def _base_metrics() -> dict:
    """Minimal metrics dict required by base.html sidebar badges."""
    insight_files = list(Path("insights").glob("*.docx")) if Path("insights").exists() else []
    tlp_files = list(Path("TLPs").glob("*.docx")) if Path("TLPs").exists() else []
    tl_outputs = _load_tl_outputs()
    social_pieces = sum(len(p.get("pieces", [])) for p in tl_outputs.values())
    return {
        "topics": len(TOPIC_LABELS),
        "insights": len(insight_files),
        "tlp_docs": len(tlp_files),
        "social_pieces": social_pieces,
    }


@tlp_insights_bp.route("/tlp")
def tlp_page():
    tl_outputs = _load_tl_outputs()
    status = _generation_status()
    return render_template(
        "v2/tlp.html",
        tl_outputs=tl_outputs,
        topic_labels=TOPIC_LABELS,
        topic_tag=TOPIC_TAG,
        platform_order=PLATFORM_ORDER,
        platform_meta=PLATFORM_META,
        status=status,
        active_page="tlp",
        active_page_title="TLP & Newsletter",
        now_label=datetime.now().strftime("%b %d, %Y"),
        metrics=_base_metrics(),
    )


@tlp_insights_bp.route("/insights")
def insights_page():
    insight_map = _load_insight_texts()
    status = _generation_status()
    return render_template(
        "v2/insights.html",
        insight_map=insight_map,
        topic_labels=TOPIC_LABELS,
        topic_tag=TOPIC_TAG,
        status=status,
        active_page="insights",
        active_page_title="Daily Insights",
        now_label=datetime.now().strftime("%b %d, %Y"),
        metrics=_base_metrics(),
    )


@tlp_insights_bp.route("/generate", methods=["POST"])
def generate():
    """
    Trigger background generation.
    JSON body: {
        "platforms": ["LinkedIn", "TikTok", ...],
        "topics": ["ai", "cybersecurity", "web3"],
        "include_tlp": true
    }
    """
    status = _generation_status()
    if status.get("running"):
        return jsonify({"ok": False, "message": "Generation already in progress."}), 409

    body = request.get_json(silent=True) or {}
    platforms = body.get("platforms", list(PLATFORM_META.keys()))
    topics = body.get("topics", list(TOPIC_LABELS.keys()))
    include_tlp = bool(body.get("include_tlp", True))

    thread = threading.Thread(
        target=_run_generation_background,
        args=(platforms, topics, include_tlp),
        daemon=True,
    )
    thread.start()

    return jsonify({"ok": True, "message": "Generation started."})


@tlp_insights_bp.route("/generation-status")
def generation_status_api():
    return jsonify(_generation_status())
