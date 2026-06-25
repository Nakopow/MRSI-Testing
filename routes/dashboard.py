import os
import json
import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, jsonify, redirect, request, session, url_for

from main import TOPIC_LABELS, extract_posting_windows, load_tlp_payloads, parse_digest_sections
from src.storage import storage

# Sample content fallback for when output.txt doesn't exist (e.g., on Vercel)
SAMPLE_OUTPUT_FILE = "sample_output.txt"

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.before_request
def _require_login():
    if not session.get("logged_in"):
        return redirect(url_for("auth.login_page", next=request.path))
PAGE_TITLES = {
    "dashboard": "Dashboard",
    "insights": "Daily Insights",
    "tlp": "TLP & Newsletter",
    "autopost": "Auto-post",
    "schedule": "Schedule",
    "apikeys": "API Keys",
    "settings": "Brand Settings",
}


def _topic_tag_class(topic_key: str) -> str:
    return {
        "ai": "tag-ai",
        "cybersecurity": "tag-cyber",
        "web3": "tag-web3",
    }.get(topic_key, "tag-ai")


def _platform_icon_class(platform_name: str) -> tuple[str, str]:
    name = (platform_name or "").lower()
    if "linkedin" in name:
        return "pi-li", "ti-brand-linkedin"
    if "instagram" in name:
        return "pi-ig", "ti-brand-instagram"
    if "facebook" in name:
        return "pi-fb", "ti-brand-facebook"
    if "tiktok" in name:
        return "pi-tt", "ti-brand-tiktok"
    if "wordpress" in name or "blog" in name:
        return "pi-wp", "ti-brand-wordpress"
    if "mail" in name or "newsletter" in name:
        return "pi-ml", "ti-mail"
    return "pi-tt", "ti-world"


def _build_dashboard_context(active_page: str = "dashboard") -> dict:
    # Try to load from cloud storage first, fall back to local filesystem, then sample
    sections = {}
    insight_files = []
    tlp_files = []
    
    # Try cloud storage first (for Vercel deployment)
    try:
        digest_content = storage.load_digest()
        if digest_content:
            # Parse digest content directly
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(digest_content)
                temp_path = f.name
            sections = parse_digest_sections(temp_path)
            os.unlink(temp_path)
        else:
            # Fall back to local or sample
            output_file = "output.txt"
            if not os.path.exists(output_file):
                if os.path.exists(SAMPLE_OUTPUT_FILE):
                    output_file = SAMPLE_OUTPUT_FILE
            sections = parse_digest_sections(output_file)
    except Exception as e:
        # Fall back to local or sample on error
        output_file = "output.txt"
        if not os.path.exists(output_file):
            if os.path.exists(SAMPLE_OUTPUT_FILE):
                output_file = SAMPLE_OUTPUT_FILE
        sections = parse_digest_sections(output_file)
    
    # Try to get TLP payloads from storage
    try:
        tlp = {}
        # Try loading from cloud storage
        for topic in ["ai", "cybersecurity", "web3"]:
            tlp_data = storage.load_tlp_json(topic)
            if tlp_data:
                tlp[topic] = tlp_data
        # Fall back to local files if no cloud data
        if not tlp:
            tlp = load_tlp_payloads()
    except Exception:
        tlp = load_tlp_payloads()
    
    # Get file lists from local filesystem (for display purposes)
    # In a full cloud implementation, these would come from storage.list_files()
    insight_files = sorted(Path("insights").glob("*.docx")) if Path("insights").exists() else []
    tlp_files = sorted(Path("TLPs").glob("*.docx")) if Path("TLPs").exists() else []

    topic_cards = []
    for key, section in sections.items():
        topic_cards.append(
            {
                "key": key,
                "label": TOPIC_LABELS.get(key, key.title()),
                "tag_class": _topic_tag_class(key),
                "title": section.get("title") or TOPIC_LABELS.get(key, key.title()),
                "briefing_line": section.get("briefing_line") or "Briefing available from the latest digest",
                "summary": section.get("summary") or ["No executive summary available yet."],
                "sources_count": len(section.get("sources", [])),
                "questions_count": len(section.get("questions", [])),
            }
        )

    recent_activity = []
    for path in insight_files[-3:]:
        recent_activity.append(
            {
                "icon_bg": "ic-green",
                "icon": "ti-file-text",
                "title": f"{path.name} is ready",
                "detail": "Daily Insight document generated from the latest digest.",
                "time": datetime.fromtimestamp(path.stat().st_mtime).strftime("%b %d, %I:%M %p"),
            }
        )
    for topic_key, payload in list(tlp.items())[:3]:
        recent_activity.append(
            {
                "icon_bg": "ic-purple",
                "icon": "ti-bulb",
                "title": f"{TOPIC_LABELS.get(topic_key, topic_key.title())} TLP loaded",
                "detail": f"{len(payload.get('pieces', []))} social pieces available for review.",
                "time": payload.get("_date", "Latest run"),
            }
        )
    recent_activity = recent_activity[:4]

    posting_windows = extract_posting_windows(tlp)
    platform_rows = []
    for window in posting_windows:
        platform_class, platform_icon = _platform_icon_class(window["platform"])
        platform_rows.append(
            {
                "platform": window["platform"],
                "topic": window["topic"],
                "note": window["note"],
                "icon_class": platform_class,
                "icon": platform_icon,
            }
        )

    if not platform_rows:
        fallback_platforms = [
            ("LinkedIn", "Waiting for posting notes from the TLP payloads."),
            ("Instagram", "Waiting for posting notes from the TLP payloads."),
            ("Facebook", "Waiting for posting notes from the TLP payloads."),
            ("TikTok", "Waiting for posting notes from the TLP payloads."),
            ("WordPress Blog", "Waiting for posting notes from the TLP payloads."),
            ("Newsletter", "Waiting for posting notes from the TLP payloads."),
        ]
        for platform, note in fallback_platforms:
            platform_class, platform_icon = _platform_icon_class(platform)
            platform_rows.append(
                {
                    "platform": platform,
                    "topic": "No topic mapped yet",
                    "note": note,
                    "icon_class": platform_class,
                    "icon": platform_icon,
                }
            )

    api_keys = [
        {
            "logo": "G",
            "name": "Google Gemini",
            "description": "Powers text summarization and image generation.",
            "connected": bool(os.environ.get("GEMINI_API_KEY")),
            "value": "Configured" if os.environ.get("GEMINI_API_KEY") else "Not configured",
            "logo_style": "background:#EFF6FF;color:#1D4ED8;",
        },
        {
            "logo": "OAI",
            "name": "OpenAI",
            "description": "Optional image and language model integration.",
            "connected": bool(os.environ.get("OPENAI_API_KEY")),
            "value": "Configured" if os.environ.get("OPENAI_API_KEY") else "Not configured",
            "logo_style": "background:#F0FDF4;color:#15803D;font-size:11px;",
        },
        {
            "logo": "MC",
            "name": "Mailchimp",
            "description": "Newsletter delivery and subscriber list workflows.",
            "connected": bool(os.environ.get("MAILCHIMP_API_KEY")),
            "value": "Configured" if os.environ.get("MAILCHIMP_API_KEY") else "Not configured",
            "logo_style": "background:#FEF9C3;color:#A16207;font-size:11px;",
        },
    ]

    metrics = {
        "topics": len(sections),
        "insights": len(insight_files),
        "tlp_docs": len(tlp_files),
        "social_pieces": sum(len(payload.get("pieces", [])) for payload in tlp.values()),
    }

    latest_run = "No generated artifacts yet"
    dated_files = insight_files + tlp_files
    if dated_files:
        latest_path = max(dated_files, key=lambda item: item.stat().st_mtime)
        latest_run = datetime.fromtimestamp(latest_path.stat().st_mtime).strftime("%b %d, %Y %I:%M %p")

    return {
        "sections": sections,
        "tlp": tlp,
        "insight_files": insight_files,
        "tlp_files": tlp_files,
        "topic_cards": topic_cards,
        "recent_activity": recent_activity,
        "platform_rows": platform_rows,
        "api_keys": api_keys,
        "metrics": metrics,
        "latest_run": latest_run,
        "now_label": datetime.now().strftime("%b %d, %Y"),
        "active_page": active_page,
        "active_page_title": PAGE_TITLES.get(active_page, "Dashboard"),
    }


def _render_dashboard(active_page: str = "dashboard"):
    return render_template("dashboard.html", **_build_dashboard_context(active_page))


@dashboard_bp.route("/")
def dashboard():
    return _render_dashboard("dashboard")


@dashboard_bp.route("/insights")
def insights():
    return _render_dashboard("insights")


@dashboard_bp.route("/tlp")
def tlp_page():
    return _render_dashboard("tlp")


@dashboard_bp.route("/autopost")
def autopost():
    return _render_dashboard("autopost")


@dashboard_bp.route("/schedule")
def schedule():
    return _render_dashboard("schedule")


@dashboard_bp.route("/apikeys")
def apikeys():
    return _render_dashboard("apikeys")


@dashboard_bp.route("/settings")
def settings():
    return _render_dashboard("settings")


# ── Settings helpers (per-user from DB, file fallback) ───────────────────────

SETTINGS_FILE = ".dashboard_settings.json"

_EMPTY_SETTINGS = lambda: {
    "autopost": {},
    "schedule": {"pipeline": [], "posting": []},
    "brand": {},
}


def _current_user():
    """Return the logged-in User ORM object, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    try:
        from models import User
        return User.query.get(user_id)
    except Exception:
        return None


def _load_settings():
    user = _current_user()
    if user:
        return user.get_settings()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return _EMPTY_SETTINGS()


def _save_settings(settings):
    user = _current_user()
    if user:
        from models import db
        user.save_settings(settings)
        db.session.commit()
    else:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)


@dashboard_bp.route("/autopost/save", methods=["POST"])
def save_autopost():
    """Save autopost settings."""
    try:
        data = request.get_json()
        if not data or "settings" not in data:
            return jsonify({"success": False, "error": "No settings provided"}), 400
        
        settings = _load_settings()
        settings["autopost"] = data["settings"]
        _save_settings(settings)
        
        return jsonify({"success": True, "message": "Autopost settings saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/schedule/config", methods=["GET"])
def get_schedule_config():
    """Return the currently saved schedule settings."""
    try:
        settings = _load_settings()
        return jsonify({"schedule": settings.get("schedule", {"pipeline": [], "posting": []})})
    except Exception as e:
        return jsonify({"schedule": {"pipeline": [], "posting": []}}), 200


@dashboard_bp.route("/schedule/save", methods=["POST"])
def save_schedule():
    """Save schedule settings and apply to the running scheduler."""
    try:
        data = request.get_json()
        if not data or "schedule" not in data:
            return jsonify({"success": False, "error": "No schedule provided"}), 400

        schedule = data["schedule"]
        settings = _load_settings()
        settings["schedule"] = schedule
        _save_settings(settings)

        # Update the live scheduler if it's running
        try:
            from src.scheduler import apply_schedule
            apply_schedule(schedule)
        except Exception:
            pass

        return jsonify({"success": True, "message": "Schedule saved and applied"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/settings/save", methods=["POST"])
def save_brand_settings():
    """Save brand settings."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No settings provided"}), 400
        
        settings = _load_settings()
        settings["brand"] = data
        _save_settings(settings)
        
        return jsonify({"success": True, "message": "Brand settings saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── API Keys Endpoint (Local Development) ────────────────────────────────────

@dashboard_bp.route("/api/keys", methods=["POST"])
def save_api_keys():
    """Save API keys — per-user in DB, then also env/cloud for pipeline use."""
    try:
        data = request.get_json()
        if not data or "keys" not in data:
            return jsonify({"success": False, "error": "No keys provided"}), 400

        keys = {k: v for k, v in data["keys"].items() if v and str(v).strip()}
        if not keys:
            return jsonify({"success": False, "error": "No non-empty keys provided"}), 400

        # Persist per-user in DB
        user = _current_user()
        if user:
            from models import db
            for key_name, value in keys.items():
                user.set_api_key(key_name, value)
            db.session.commit()

        # Also write to env so the pipeline picks them up this session
        for key_name, value in keys.items():
            _save_key_to_env(key_name, value)

        return jsonify({"success": True, "message": "API keys saved successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/api/keys/test/<key_name>", methods=["POST"])
def test_api_key(key_name):
    """Test if an API key is valid by making a real API call."""
    try:
        data = request.get_json()
        if not data or "key" not in data:
            return jsonify({"success": False, "error": "No API key provided"}), 400
        
        api_key = data["key"]
        if not api_key or len(api_key.strip()) < 10:
            return jsonify({"success": False, "error": "Invalid API key format"}), 400
        
        key_name_lower = key_name.lower()
        
        if "gemini" in key_name_lower or "google" in key_name_lower:
            return _test_gemini_key(api_key)
        elif "openai" in key_name_lower:
            return _test_openai_key(api_key)
        elif "mailchimp" in key_name_lower:
            return _test_mailchimp_key(api_key)
        else:
            return jsonify({"success": False, "error": f"Unknown key type: {key_name}"}), 400
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _test_gemini_key(api_key):
    """Test Gemini API key by making a simple API call and save if valid."""
    try:
        import urllib.request
        import json
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:list?key={api_key}"
        
        req = urllib.request.Request(url)
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                # Key is valid - save it to .env
                _save_key_to_env("GEMINI_API_KEY", api_key)
                return jsonify({
                    "success": True, 
                    "message": "Gemini API key is valid, saved, and connected.",
                    "service": "Google Gemini",
                    "saved": True
                })
    except urllib.error.HTTPError as e:
        error_msg = f"Invalid Gemini API key (HTTP {e.code})"
        if e.code == 403:
            error_msg = "Invalid or expired Gemini API key"
        elif e.code == 400:
            error_msg = "Invalid Gemini API key format"
        return jsonify({"success": False, "error": error_msg})
    except urllib.error.URLError as e:
        return jsonify({"success": False, "error": f"Connection error: {str(e.reason)}"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Test failed: {str(e)}"})


def _test_openai_key(api_key):
    """Test OpenAI API key by making a simple API call and save if valid."""
    try:
        import urllib.request
        import json
        
        url = "https://api.openai.com/v1/models"
        
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                # Key is valid - save it to .env
                _save_key_to_env("OPENAI_API_KEY", api_key)
                return jsonify({
                    "success": True, 
                    "message": "OpenAI API key is valid, saved, and connected.",
                    "service": "OpenAI",
                    "saved": True
                })
    except urllib.error.HTTPError as e:
        error_msg = f"Invalid OpenAI API key (HTTP {e.code})"
        if e.code == 401:
            error_msg = "Invalid or expired OpenAI API key"
        elif e.code == 429:
            error_msg = "OpenAI API rate limit reached"
        return jsonify({"success": False, "error": error_msg})
    except urllib.error.URLError as e:
        return jsonify({"success": False, "error": f"Connection error: {str(e.reason)}"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Test failed: {str(e)}"})


def _test_mailchimp_key(api_key):
    """Test Mailchimp API key by making a simple API call and save if valid."""
    try:
        import urllib.request
        import json
        import base64
        
        # Mailchimp API key format is "apikey-datacenter"
        if "-" not in api_key:
            return jsonify({
                "success": False, 
                "error": "Invalid Mailchimp API key format (expected: apikey-datacenter)"
            })
        
        dc = api_key.split('-')[-1]
        url = f"https://{dc}.api.mailchimp.com/3.0/"
        
        req = urllib.request.Request(url)
        req.add_header('Authorization', f'apikey {api_key}')
        req.add_header('Content-Type', 'application/json')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                # Key is valid - save it to .env
                _save_key_to_env("MAILCHIMP_API_KEY", api_key)
                return jsonify({
                    "success": True, 
                    "message": "Mailchimp API key is valid, saved, and connected.",
                    "service": "Mailchimp",
                    "saved": True
                })
    except urllib.error.HTTPError as e:
        error_msg = f"Invalid Mailchimp API key (HTTP {e.code})"
        if e.code == 401:
            error_msg = "Invalid or expired Mailchimp API key"
        return jsonify({"success": False, "error": error_msg})
    except urllib.error.URLError as e:
        return jsonify({"success": False, "error": f"Connection error: {str(e.reason)}"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Test failed: {str(e)}"})


def _save_key_to_env(key_name, value):
    """Save a single API key to .env file (local) or cloud storage (Vercel)."""
    try:
        # Check if running on Vercel or if cloud storage is configured
        is_vercel = os.getenv("VERCEL") == "1"
        has_supabase = os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")
        
        if is_vercel or (has_supabase and os.getenv("STORAGE_BACKEND") != "local"):
            # Use cloud storage for Vercel deployment
            return _save_key_to_cloud(key_name, value)
        else:
            # Use local .env file for development
            from dotenv import set_key
            from pathlib import Path
            
            dotenv_path = Path(__file__).parent.parent / ".env"
            set_key(str(dotenv_path), key_name, value)
            
            # Update environment variable for current session
            os.environ[key_name] = value
            
            return True
    except Exception as e:
        print(f"Error saving {key_name}: {e}")
        return False


def _save_key_to_cloud(key_name, value):
    """Save API key to cloud storage (Supabase) for Vercel deployment."""
    try:
        import json
        from src.storage import storage
        
        # Load existing keys from cloud storage
        keys_data = {}
        try:
            content = storage.backend.load(".api_keys.json")
            if content:
                keys_data = json.loads(content)
        except Exception:
            pass
        
        # Update the specific key
        if "keys" not in keys_data:
            keys_data["keys"] = {}
        keys_data["keys"][key_name] = value
        keys_data["updated_at"] = datetime.now().isoformat()
        
        # Save back to cloud storage
        success = storage.backend.save(
            ".api_keys.json",
            json.dumps(keys_data, indent=2),
            content_type="application/json"
        )
        
        if success:
            # Also update environment variable for current session
            os.environ[key_name] = value
        
        return success
    except Exception as e:
        print(f"Error saving {key_name} to cloud: {e}")
        return False


@dashboard_bp.route("/api/keys/config", methods=["GET"])
def get_api_keys_config():
    """Get API keys configuration status."""
    try:
        # Determine storage type
        storage_type = os.getenv("STORAGE_BACKEND", "local")
        if storage_type == "auto":
            if os.getenv("SUPABASE_URL"):
                storage_type = "Supabase Storage"
            elif os.getenv("AWS_ACCESS_KEY_ID"):
                storage_type = "AWS S3"
            else:
                storage_type = "Local (.env file)"
        
        return jsonify({
            "storage_type": storage_type,
            "keys": {
                "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
                "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
                "MAILCHIMP_API_KEY": bool(os.getenv("MAILCHIMP_API_KEY")),
            }
        })
    except Exception:
        return jsonify({
            "storage_type": "Local (.env file)",
            "keys": {}
        })


# ── TLP Management Endpoints ─────────────────────────────────────────────────

@dashboard_bp.route("/tlp/save", methods=["POST"])
def save_tlp_edit():
    """Save edited TLP content."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        topic = data.get("topic", "")
        piece_index = data.get("pieceIndex", 0)
        angle = data.get("angle", "")
        content = data.get("content", "")
        posting_notes = data.get("posting_notes", "")
        
        # Load the TLP JSON file for this topic
        tlp_file = Path(f"tl_output_{topic}.json")
        if not tlp_file.exists():
            # Create a new TLP structure if it doesn't exist
            tlp_data = {"pieces": []}
        else:
            with open(tlp_file, "r", encoding="utf-8") as f:
                tlp_data = json.load(f)
        
        # Ensure pieces array exists
        if "pieces" not in tlp_data:
            tlp_data["pieces"] = []
        
        # Update or create the piece at the given index
        piece_data = {
            "platform": data.get("platform", "Custom"),
            "angle": angle,
            "copy": content,
            "posting_notes": posting_notes,
            "format": "Edited",
        }
        
        if piece_index < len(tlp_data["pieces"]):
            # Update existing piece (preserve other fields)
            tlp_data["pieces"][piece_index].update(piece_data)
        else:
            # Add new piece
            tlp_data["pieces"].append(piece_data)
        
        # Save back to file
        with open(tlp_file, "w", encoding="utf-8") as f:
            json.dump(tlp_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({"success": True, "message": "TLP content saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@dashboard_bp.route("/tlp/post", methods=["POST"])
def post_tlp():
    """Trigger posting of a TLP piece to the platform."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        topic = data.get("topic", "")
        piece_index = data.get("pieceIndex", 0)
        
        # Log the posting request (in a real implementation, this would trigger actual posting)
        logger = logging.getLogger(__name__)
        logger.info(f"Post requested for topic={topic}, piece_index={piece_index}")
        
        # For now, return success with a note that platform integration is needed
        return jsonify({
            "success": True, 
            "message": "Post queued - platform integration required for actual posting"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Topic Management Endpoints ───────────────────────────────────────────────

TOPICS_FILE = ".custom_topics.json"


@dashboard_bp.route("/topics/add", methods=["POST"])
def add_topic():
    """Add a new custom topic to the dashboard."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        name = data.get("name", "")
        key = data.get("key", "")
        feeds = data.get("feeds", [])
        color = data.get("color", "#6B3FA0")
        
        if not name or not key:
            return jsonify({"success": False, "error": "Topic name and key are required"}), 400
        
        if not feeds or not isinstance(feeds, list):
            return jsonify({"success": False, "error": "At least one RSS feed is required"}), 400
        
        # Load existing topics
        topics = _load_custom_topics()
        
        # Check if key already exists
        if key in topics:
            return jsonify({"success": False, "error": "A topic with this key already exists"}), 400
        
        # Add new topic
        topics[key] = {
            "name": name,
            "key": key,
            "feeds": feeds,
            "color": color,
            "created_at": datetime.now().isoformat(),
        }
        
        # Save updated topics
        _save_custom_topics(topics)
        
        # Update feeds.json with new topic feeds
        _update_feeds_json(key, name, feeds)
        
        return jsonify({"success": True, "message": f"Topic '{name}' added successfully"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _load_custom_topics():
    """Load custom topics from file."""
    try:
        with open(TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_custom_topics(topics):
    """Save custom topics to file."""
    with open(TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2)


def _update_feeds_json(topic_key, topic_name, feeds):
    """Update feeds.json with new topic feeds."""
    feeds_file = Path("feeds.json")
    
    try:
        if feeds_file.exists():
            with open(feeds_file, "r", encoding="utf-8") as f:
                feeds_data = json.load(f)
        else:
            feeds_data = {}
        
        # Add new topic feeds
        feeds_data[topic_key] = {
            "name": topic_name,
            "urls": feeds
        }
        
        with open(feeds_file, "w", encoding="utf-8") as f:
            json.dump(feeds_data, f, indent=2)
    except Exception:
        # Don't fail the whole operation if feeds.json update fails
        pass
