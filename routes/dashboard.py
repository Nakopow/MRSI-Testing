import os
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template

from main import TOPIC_LABELS, extract_posting_windows, load_tlp_payloads, parse_digest_sections

dashboard_bp = Blueprint("dashboard", __name__)
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
    sections = parse_digest_sections("output.txt")
    tlp = load_tlp_payloads()
    insight_files = sorted(Path("insights").glob("*.docx"))
    tlp_files = sorted(Path("TLPs").glob("*.docx"))

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
