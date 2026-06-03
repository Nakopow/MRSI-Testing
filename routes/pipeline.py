import os
import json
import threading
import logging
from datetime import datetime
from pathlib import Path
from flask import Blueprint, jsonify, request

# Import pipeline components
from scraper_main import main as run_scraping
from summarizer import generate_daily_digest
from main import run_formatter, run_tl_pipeline, parse_digest_sections, load_tlp_payloads
from src.storage import storage

pipeline_bp = Blueprint("pipeline", __name__)
logger = logging.getLogger(__name__)

# ── Pipeline State Management ──────────────────────────────────────────────────

STATE_FILE = ".pipeline_state.json"

def _load_state():
    """Load pipeline state from file."""
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "scraping": {"status": "idle", "last_run": None, "last_duration": None},
            "summarizing": {"status": "idle", "last_run": None, "last_duration": None},
            "insights": {"status": "idle", "last_run": None, "last_duration": None},
            "tlp": {"status": "idle", "last_run": None, "last_duration": None},
        }

def _save_state(state):
    """Save pipeline state to file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def _update_step_status(step, status, duration=None):
    """Update the status of a pipeline step."""
    state = _load_state()
    if step in state:
        state[step]["status"] = status
        if status == "idle" and duration is not None:
            state[step]["last_run"] = datetime.now().isoformat()
            state[step]["last_duration"] = round(duration, 2)
    _save_state(state)

# ── Helper Functions ───────────────────────────────────────────────────────────

def _check_articles_exist():
    """Check if article files exist from scraping (local or cloud storage)."""
    topics = ["ai", "cybersecurity", "web3"]
    # Check local files first
    for topic in topics:
        if os.path.exists(f"{topic}_articles.txt"):
            return True
    # Check cloud storage
    try:
        return all(storage.backend.exists(f"articles/{topic}_articles.txt") for topic in topics)
    except Exception:
        return False

def _check_digest_exists():
    """Check if output.txt exists from summarization (local or cloud storage)."""
    if os.path.exists("output.txt"):
        return True
    try:
        return storage.backend.exists("output.txt")
    except Exception:
        return False

# ── Pipeline Step Routes ──────────────────────────────────────────────────────

@pipeline_bp.route("/status")
def pipeline_status():
    """Get current status of all pipeline stages."""
    state = _load_state()
    
    # Add artifact availability
    state["artifacts"] = {
        "articles_scraped": _check_articles_exist(),
        "digest_generated": _check_digest_exists(),
        "insights_count": len(list(Path("insights").glob("*.docx"))),
        "tlp_count": len(list(Path("TLPs").glob("*.docx"))),
    }
    
    return jsonify(state)


@pipeline_bp.route("/scrape", methods=["POST"])
def scrape_articles():
    """
    Step 1: Scrape RSS feeds and save article files.
    
    This runs the scraping pipeline which:
    - Fetches RSS feeds from feeds.json
    - Enriches articles with full text
    - Saves to ai_articles.txt, cybersecurity_articles.txt, web3_articles.txt
    """
    if request.method == "POST":
        _update_step_status("scraping", "running")
        
        def run_scrape_task():
            import time
            start = time.time()
            try:
                logger.info("Starting scraping pipeline...")
                run_scraping()
                duration = time.time() - start
                _update_step_status("scraping", "idle", duration)
                logger.info(f"Scraping completed in {duration:.2f}s")
            except Exception as e:
                logger.error(f"Scraping failed: {e}")
                _update_step_status("scraping", "error")
        
        thread = threading.Thread(target=run_scrape_task)
        thread.start()
        
        return jsonify({
            "status": "started",
            "step": "scraping",
            "message": "Scraping pipeline started. Articles will be saved to topic files."
        })
    
    return jsonify({"error": "Method not allowed"}), 405


@pipeline_bp.route("/summarize", methods=["POST"])
def generate_summary():
    """
    Step 2: Generate daily digest from scraped articles.
    
    This runs the summarization pipeline which:
    - Reads article files (ai_articles.txt, etc.)
    - Calls Gemini AI to generate summaries
    - Saves output to output.txt
    """
    if request.method == "POST":
        # Check prerequisites
        if not _check_articles_exist():
            return jsonify({
                "error": "Article files not found. Please run scraping first.",
                "required_step": "scraping"
            }), 400
        
        _update_step_status("summarizing", "running")
        
        def run_summarize_task():
            import time
            start = time.time()
            try:
                logger.info("Starting summarization pipeline...")
                
                # Load articles by topic
                articles_by_topic = {}
                topics = ["ai", "cybersecurity", "web3"]
                for topic in topics:
                    filename = f"{topic}_articles.txt"
                    content = None
                    # Try local file first
                    if os.path.exists(filename):
                        with open(filename, "r", encoding="utf-8") as f:
                            content = f.read()
                    # Fall back to cloud storage
                    elif storage.backend.exists(f"articles/{topic}_articles.txt"):
                        content = storage.backend.load(f"articles/{topic}_articles.txt")
                    
                    if content:
                        # Parse articles from file - extract title, published, body from formatted text
                        articles = []
                        lines = content.split("\n")
                        i = 0
                        while i < len(lines):
                            line = lines[i].strip()
                            # Look for article title (starts with quote)
                            if line.startswith('"') and line.endswith('"'):
                                title = line.strip('"')
                                # Next line should be the date
                                published = ""
                                if i + 1 < len(lines):
                                    published = lines[i + 1].strip()
                                    i += 1
                                # Skip empty lines and collect body until we hit a URL or separator
                                body_lines = []
                                i += 1
                                while i < len(lines):
                                    body_line = lines[i].strip()
                                    # Stop at URL (starts with http) or separator (===)
                                    if body_line.startswith("http") or body_line.startswith("=" * 10):
                                        break
                                    if body_line:
                                        body_lines.append(body_line)
                                    i += 1
                                if title and body_lines:
                                    articles.append({
                                        "title": title,
                                        "published": published,
                                        "body": " ".join(body_lines)
                                    })
                            i += 1
                        # If no articles parsed, use the whole content as fallback
                        if not articles:
                            articles = [{"title": f"{topic} articles", "published": "Unknown", "body": content}]
                        articles_by_topic[topic] = articles
                
                # Generate digest
                digest = generate_daily_digest(articles_by_topic)
                
                # Save to local file AND cloud storage
                with open("output.txt", "w", encoding="utf-8") as f:
                    f.write(digest)
                # Also save to cloud storage for Vercel
                try:
                    storage.save_digest(digest)
                except Exception as e:
                    logger.warning(f"Failed to save digest to cloud storage: {e}")
                
                duration = time.time() - start
                _update_step_status("summarizing", "idle", duration)
                logger.info(f"Summarization completed in {duration:.2f}s")
            except Exception as e:
                logger.error(f"Summarization failed: {e}")
                _update_step_status("summarizing", "error")
        
        thread = threading.Thread(target=run_summarize_task)
        thread.start()
        
        return jsonify({
            "status": "started",
            "step": "summarizing",
            "message": "Summarization pipeline started. Daily digest will be saved to output.txt."
        })
    
    return jsonify({"error": "Method not allowed"}), 405


@pipeline_bp.route("/insights", methods=["POST"])
def generate_daily_insights():
    """
    Step 3: Generate Daily Insight DOCX files (on-demand).
    
    This runs the formatter which:
    - Reads output.txt
    - Generates branded Daily Insight DOCX files per topic
    - Saves to insights/ folder
    NOTE: This ONLY generates Daily Insights, NOT TLPs.
    """
    if request.method == "POST":
        # Check prerequisites
        if not _check_digest_exists():
            return jsonify({
                "error": "Daily digest (output.txt) not found. Please run summarization first.",
                "required_step": "summarizing"
            }), 400
        
        _update_step_status("insights", "running")
        
        def run_insights_task():
            import time
            start = time.time()
            try:
                logger.info("Starting Daily Insights generation (ONLY - not TLPs)...")
                run_formatter("output.txt")
                duration = time.time() - start
                _update_step_status("insights", "idle", duration)
                logger.info(f"Daily Insights generation completed in {duration:.2f}s")
            except Exception as e:
                logger.error(f"Daily Insights generation failed: {e}")
                _update_step_status("insights", "error")
        
        thread = threading.Thread(target=run_insights_task)
        thread.start()
        
        return jsonify({
            "status": "started",
            "step": "insights",
            "message": "Daily Insights generation started. ONLY generating insights, NOT TLPs."
        })
    
    return jsonify({"error": "Method not allowed"}), 405


@pipeline_bp.route("/insights/download", methods=["GET"])
def download_insights():
    """
    Download all Daily Insight DOCX files as a ZIP archive.
    """
    from flask import send_file
    import zipfile
    import io
    
    insights_dir = Path("insights")
    if not insights_dir.exists():
        return jsonify({"error": "No insights available"}), 404
    
    docx_files = list(insights_dir.glob("*.docx"))
    if not docx_files:
        return jsonify({"error": "No DOCX files found in insights folder"}), 404
    
    # Create ZIP in memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in docx_files:
            zf.write(file_path, file_path.name)
    
    memory_file.seek(0)
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='daily_insights.zip'
    )


@pipeline_bp.route("/insights/download/<filename>", methods=["GET"])
def download_single_insight(filename):
    """
    Download a single Daily Insight DOCX file.
    """
    from flask import send_file
    
    file_path = Path("insights") / filename
    
    # Security check: ensure filename doesn't contain path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({"error": "Invalid filename"}), 400
    
    if not file_path.exists():
        return jsonify({"error": "File not found"}), 404
    
    return send_file(
        file_path,
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        as_attachment=True,
        download_name=filename
    )


@pipeline_bp.route("/tlp", methods=["POST"])
def generate_tlp():
    """
    Step 4: Generate Thought Leadership packs (on-demand).
    
    This runs the TL pipeline which:
    - Reads output.txt
    - Calls Gemini to generate social media content
    - Generates platform-specific pieces (LinkedIn, Instagram, etc.)
    - Saves JSON payloads and DOCX files to TLPs/ folder
    
    Accepts optional JSON body with:
    - platforms: list of platform names to generate (default: all)
    - topic: topic to generate for (default: all)
    """
    if request.method == "POST":
        # Check prerequisites
        if not _check_digest_exists():
            return jsonify({
                "error": "Daily digest (output.txt) not found. Please run summarization first.",
                "required_step": "summarizing"
            }), 400
        
        # Parse optional platform and topic filters from request body
        platforms = None
        topic = None
        
        if request.is_json:
            data = request.get_json(silent=True) or {}
            platforms = data.get("platforms")  # List of platform names or None for all
            topic = data.get("topic")  # Single topic or "all"
        
        _update_step_status("tlp", "running")
        
        def run_tlp_task():
            import time
            start = time.time()
            try:
                platform_str = f" (platforms: {', '.join(platforms)})" if platforms else ""
                topic_str = f" (topic: {topic})" if topic and topic != "all" else ""
                logger.info(f"Starting Thought Leadership pipeline{platform_str}{topic_str}...")
                
                # Pass parameters to the TL pipeline
                run_tl_pipeline("output.txt", platforms=platforms, topic=topic)
                
                duration = time.time() - start
                _update_step_status("tlp", "idle", duration)
                logger.info(f"Thought Leadership pipeline completed in {duration:.2f}s")
            except Exception as e:
                logger.error(f"Thought Leadership pipeline failed: {e}")
                _update_step_status("tlp", "error")
        
        thread = threading.Thread(target=run_tlp_task)
        thread.start()
        
        platform_msg = f" for platforms: {', '.join(platforms)}" if platforms else ""
        topic_msg = f" (topic: {topic})" if topic and topic != "all" else ""
        
        return jsonify({
            "status": "started",
            "step": "tlp",
            "message": f"Thought Leadership pipeline started{platform_msg}{topic_msg}. Content packs will be saved to TLPs/ folder."
        })
    
    return jsonify({"error": "Method not allowed"}), 405


@pipeline_bp.route("/run-all", methods=["POST"])
def run_full_pipeline():
    """
    Run the complete pipeline (original behavior).
    
    This runs all steps in sequence:
    1. Scrape RSS feeds
    2. Generate daily digest
    3. Generate Daily Insights
    4. Generate Thought Leadership packs
    """
    if request.method == "POST":
        def run_all_tasks():
            import time
            start = time.time()
            try:
                logger.info("Starting full pipeline...")
                
                # Step 1: Scrape
                _update_step_status("scraping", "running")
                run_scraping()
                _update_step_status("scraping", "idle", time.time() - start)
                
                # Step 2: Summarize
                _update_step_status("summarizing", "running")
                articles_by_topic = {}
                topics = ["ai", "cybersecurity", "web3"]
                for topic in topics:
                    filename = f"{topic}_articles.txt"
                    if os.path.exists(filename):
                        with open(filename, "r", encoding="utf-8") as f:
                            content = f.read()
                        # Parse articles from file - extract title, published, body from formatted text
                        articles = []
                        lines = content.split("\n")
                        i = 0
                        while i < len(lines):
                            line = lines[i].strip()
                            # Look for article title (starts with quote)
                            if line.startswith('"') and line.endswith('"'):
                                title = line.strip('"')
                                # Next line should be the date
                                published = ""
                                if i + 1 < len(lines):
                                    published = lines[i + 1].strip()
                                    i += 1
                                # Skip empty lines and collect body until we hit a URL or separator
                                body_lines = []
                                i += 1
                                while i < len(lines):
                                    body_line = lines[i].strip()
                                    # Stop at URL (starts with http) or separator (===)
                                    if body_line.startswith("http") or body_line.startswith("=" * 10):
                                        break
                                    if body_line:
                                        body_lines.append(body_line)
                                    i += 1
                                if title and body_lines:
                                    articles.append({
                                        "title": title,
                                        "published": published,
                                        "body": " ".join(body_lines)
                                    })
                            i += 1
                        # If no articles parsed, use the whole content as fallback
                        if not articles:
                            articles = [{"title": f"{topic} articles", "published": "Unknown", "body": content}]
                        articles_by_topic[topic] = articles
                
                digest = generate_daily_digest(articles_by_topic)
                with open("output.txt", "w", encoding="utf-8") as f:
                    f.write(digest)
                _update_step_status("summarizing", "idle", time.time() - start)
                
                # Step 3: Generate Insights
                _update_step_status("insights", "running")
                run_formatter("output.txt")
                _update_step_status("insights", "idle", time.time() - start)
                
                # Step 4: Generate TLP
                _update_step_status("tlp", "running")
                run_tl_pipeline("output.txt")
                _update_step_status("tlp", "idle", time.time() - start)
                
                logger.info(f"Full pipeline completed in {time.time() - start:.2f}s")
            except Exception as e:
                logger.error(f"Full pipeline failed: {e}")
                # Update all remaining steps to error
                for step in ["scraping", "summarizing", "insights", "tlp"]:
                    state = _load_state()
                    if state.get(step, {}).get("status") == "running":
                        _update_step_status(step, "error")
        
        thread = threading.Thread(target=run_all_tasks)
        thread.start()
        
        return jsonify({
            "status": "started",
            "step": "full-pipeline",
            "message": "Full pipeline started. All steps will run in sequence."
        })
    
    return jsonify({"error": "Method not allowed"}), 405


# ── Legacy Route (for backward compatibility) ──────────────────────────────────

@pipeline_bp.route("/run", methods=["POST"])
def run_legacy():
    """Legacy route that runs the full pipeline (redirects to /run-all)."""
    return run_full_pipeline()