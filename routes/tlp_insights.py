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


def _extract_date_from_filename(filename: str) -> str | None:
    """
    Extract date from insight filename patterns like:
    - Exoasia_MRSI_DailyInsight_Jun01_AI.docx
    - Exoasia_MRSI_DailyInsight_Jun02_CyberSec.docx
    
    Returns date string in "Month DD, YYYY" format or None if not found.
    """
    import re
    
    # Pattern to match month abbreviation followed by 1-2 digits
    # e.g., "Jun01", "Jun02", "Mar9", "Dec25"
    pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(\d{1,2})'
    match = re.search(pattern, filename)
    
    if match:
        month_abbr = match.group(1)
        day = int(match.group(2))
        
        # Use current year since filenames don't include year
        current_year = datetime.now().year
        
        # Create datetime object and format it properly
        try:
            date_obj = datetime.strptime(f"{month_abbr} {day} {current_year}", "%b %d %Y")
            return date_obj.strftime("%B %d, %Y")
        except ValueError:
            return None
    
    return None


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

            # Extract date from filename instead of using file modification time
            date_str = _extract_date_from_filename(p.name)
            if date_str is None:
                # Fallback to modification time if date extraction fails
                mtime = datetime.fromtimestamp(p.stat().st_mtime)
                date_str = mtime.strftime("%B %d, %Y")
            
            existing_dates = {e.get("date") for e in insight_map[matched_key]}
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
    """Return a detailed status dict for the last generation run."""
    status_file = Path(".generation_status.json")
    if status_file.exists():
        try:
            with open(status_file) as f:
                data = json.load(f)
                # Ensure all expected fields exist
                return {
                    "running": data.get("running", False),
                    "last_run": data.get("last_run"),
                    "message": data.get("message", "Unknown"),
                    "progress": data.get("progress", 0),
                    "stage": data.get("stage", ""),
                    "insights_generated": data.get("insights_generated", 0),
                    "tlps_generated": data.get("tlps_generated", 0),
                }
        except Exception:
            pass
    return {
        "running": False,
        "last_run": None,
        "message": "Never run",
        "progress": 0,
        "stage": "",
        "insights_generated": 0,
        "tlps_generated": 0,
    }


def _set_generation_status(
    running: bool,
    message: str,
    progress: int = 0,
    stage: str = "",
    insights_generated: int = None,
    tlps_generated: int = None,
) -> None:
    status_file = Path(".generation_status.json")
    existing = _generation_status()

    data = {
        "running": running,
        "last_run": (
            datetime.now().isoformat()
            if not running
            else existing.get("last_run")
        ),
        "message": message,
        "progress": progress,
        "stage": stage,
        "insights_generated": (
            insights_generated
            if insights_generated is not None
            else existing.get("insights_generated", 0)
        ),
        "tlps_generated": (
            tlps_generated
            if tlps_generated is not None
            else existing.get("tlps_generated", 0)
        ),
    }
    with open(status_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _run_generation_background(platforms: list[str], topics: list[str], include_tlp: bool = True) -> None:
    """
    Called in a background thread. Runs the pipeline for insights and,
    optionally, the TLP pipeline. Uses the pipeline components directly
    instead of calling main.main() for better web compatibility.
    """
    import json as json_module
    
    try:
        # Stage 1: Run insight pipeline (0-50%)
        _set_generation_status(
            True, "Running insight pipeline...",
            progress=5, stage="Starting pipeline"
        )

        try:
            # Import pipeline components
            from scraper_main import main as run_scraping
            from summarizer import generate_daily_digest
            from main import run_formatter
            
            _set_generation_status(
                True, "Loading feeds from feeds.json...",
                progress=10, stage="Loading feeds"
            )
            
            # Load feeds
            with open("feeds.json", "r", encoding="utf-8") as f:
                feeds = json_module.load(f)
            
            _set_generation_status(
                True, "Scraping articles from RSS feeds...",
                progress=15, stage="Scraping"
            )
            
            # Run scraping
            from scraper import enrich_articles, fetch_rss_items, load_url_cache
            URL_CACHE_FILE = ".url_cache.json"
            
            url_cache = load_url_cache(URL_CACHE_FILE)
            raw_items = fetch_rss_items(feeds)
            enriched = enrich_articles(raw_items, url_cache, cache_file=URL_CACHE_FILE)
            
            # Group by topic
            articles_by_topic = {}
            for article in enriched:
                topic = article.get("topic", "unknown")
                if topic not in articles_by_topic:
                    articles_by_topic[topic] = []
                articles_by_topic[topic].append(article)
            
            _set_generation_status(
                True, "Generating AI summaries...",
                progress=30, stage="Summarizing"
            )
            
            # Generate digest
            digest = generate_daily_digest(articles_by_topic)
            
            # Save output.txt
            with open("output.txt", "w", encoding="utf-8") as f:
                f.write(digest)
            
            _set_generation_status(
                True, "Formatting Daily Insights...",
                progress=45, stage="Formatting"
            )
            
            # Run formatter
            run_formatter("output.txt")

            # Count generated insights
            insight_count = len(list(Path("insights").glob("*.docx"))) if Path("insights").exists() else 0
            _set_generation_status(
                True, f"Daily Insights generated ({insight_count} files)",
                progress=50, stage="Insights complete",
                insights_generated=insight_count
            )
        except Exception as e:
            _set_generation_status(
                False, f"Insight pipeline error: {str(e)}",
                progress=0, stage="Error"
            )
            return

        if not include_tlp:
            _set_generation_status(
                False,
                f"Daily Insights ready - {datetime.now().strftime('%b %d, %Y %I:%M %p')}",
                progress=100, stage="Complete",
                insights_generated=len(list(Path("insights").glob("*.docx"))) if Path("insights").exists() else 0
            )
            return

        # Stage 2: Run TLP pipeline (50-100%)
        _set_generation_status(
            True, "Running TLP pipeline...",
            progress=55, stage="Starting TLP generation"
        )

        try:
            import tl_summarizer as tlsum
            import tl_formatter

            _set_generation_status(
                True, "Generating thought leadership content...",
                progress=60, stage="Generating TLPs"
            )
            
            # Run TL summarizer
            gemini_key = None
            import os
            gemini_key = os.environ.get("GEMINI_API_KEY")
            if not gemini_key:
                raise EnvironmentError("GEMINI_API_KEY environment variable is not set")
            
            prompts_path = "tl_prompts_config.json"
            json_files = tlsum.summarize_tl(
                gemini_key=gemini_key,
                output_txt="output.txt",
                prompts_path=prompts_path,
                outdir=".",
            )

            _set_generation_status(
                True, "Applying platform filters...",
                progress=80, stage="Filtering platforms"
            )

            # Count and filter generated TLPs
            tlp_count = 0
            if platforms:
                for key in topics:
                    out_path = Path(f"tl_output_{key}.json")
                    if out_path.exists():
                        with open(out_path, encoding="utf-8") as f:
                            data = json_module.load(f)
                        filtered_pieces = [
                            p
                            for p in data.get("pieces", [])
                            if any(pl.lower() in p.get("platform", "").lower() for pl in platforms)
                        ]
                        tlp_count += len(filtered_pieces)
                        data["pieces"] = filtered_pieces
                        with open(out_path, "w", encoding="utf-8") as f:
                            json_module.dump(data, f, ensure_ascii=False, indent=2)
            else:
                # Count all TLP pieces
                for key in topics:
                    out_path = Path(f"tl_output_{key}.json")
                    if out_path.exists():
                        with open(out_path, encoding="utf-8") as f:
                            data = json.load(f)
                        tlp_count += len(data.get("pieces", []))

            _set_generation_status(
                True, f"Generated {tlp_count} TLP pieces",
                progress=95, stage="Finalizing",
                tlps_generated=tlp_count
            )

            _set_generation_status(
                False,
                f"TLPs ready - {datetime.now().strftime('%b %d, %Y %I:%M %p')} - {tlp_count} pieces",
                progress=100, stage="Complete",
                tlps_generated=tlp_count
            )
        except Exception as e:
            _set_generation_status(
                False, f"TLP pipeline error: {e}",
                progress=50, stage="Error"
            )
            return

    except Exception as e:
        _set_generation_status(
            False, f"Unexpected error: {e}",
            progress=0, stage="Error"
        )


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
    
    # Find the latest insight date across all topics to display in the header
    latest_date = None
    for entries in insight_map.values():
        for entry in entries:
            date_str = entry.get("date", "")
            if date_str:
                try:
                    date_obj = datetime.strptime(date_str, "%B %d, %Y")
                    if latest_date is None or date_obj > latest_date:
                        latest_date = date_obj
                except ValueError:
                    pass
    
    # Format the latest date for display, or use today if no insights found
    if latest_date:
        now_label = latest_date.strftime("%b %d, %Y")
    else:
        now_label = datetime.now().strftime("%b %d, %Y")
    
    return render_template(
        "v2/insights.html",
        insight_map=insight_map,
        topic_labels=TOPIC_LABELS,
        topic_tag=TOPIC_TAG,
        status=status,
        active_page="insights",
        active_page_title="Daily Insights",
        now_label=now_label,
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
