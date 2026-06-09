"""
src/scheduler.py

APScheduler integration for automated pipeline runs.
Only active on Railway/long-running deployments; skipped on Vercel serverless.

Schedule settings are read from .settings.json (saved by the dashboard) and
applied to a BackgroundScheduler on startup and whenever the user saves new
schedule settings.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_scheduler = None  # BackgroundScheduler instance, or None if not initialized


# ── Parsing helpers ───────────────────────────────────────────────────────────

def _parse_schedule_entry(entry: dict) -> tuple[Optional[str], int, int]:
    """
    Parse a schedule entry dict into (day_of_week, hour, minute).

    Handles formats produced by the dashboard UI:
      "6:00 AM PHT"  → (None, 6, 0)   daily
      "Mon 6:00 AM"  → ('mon', 6, 0)  weekly on Monday
      "On-demand"    → (None, -1, -1) means no scheduled job

    Returns (None, -1, -1) when no job should be scheduled.
    """
    label = entry.get("label", "")
    time_str = entry.get("time", "").strip()

    if "Manual" in label or "demand" in time_str.lower():
        return None, -1, -1

    parts = time_str.split()

    day_of_week: Optional[str] = None
    _days = {
        "Mon": "mon", "Tue": "tue", "Wed": "wed", "Thu": "thu",
        "Fri": "fri", "Sat": "sat", "Sun": "sun",
    }
    if parts and parts[0] in _days:
        day_of_week = _days[parts[0]]
        parts = parts[1:]

    # parts now like ["6:00", "AM"] or ["6:00", "AM", "PHT"]
    time_part = parts[0] if parts else "6:00"
    ampm = parts[1].upper() if len(parts) > 1 else "AM"

    if ":" in time_part:
        h_str, m_str = time_part.split(":", 1)
    else:
        h_str, m_str = time_part, "0"

    hour = int(h_str)
    minute = int(m_str)

    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0

    return day_of_week, hour, minute


# ── Pipeline job ──────────────────────────────────────────────────────────────

def _run_pipeline_job() -> None:
    """APScheduler job: runs the full pipeline in the scheduler thread."""
    logger.info("Scheduler: starting scheduled pipeline run")
    try:
        from routes.tlp_insights import _run_generation_background  # type: ignore
        platforms = [
            "LinkedIn",
            "YouTube / Video Script",
            "Instagram Carousel",
            "Facebook",
            "TikTok",
        ]
        topics = ["ai", "cybersecurity", "web3"]
        _run_generation_background(platforms, topics, include_tlp=True)
        logger.info("Scheduler: scheduled pipeline run complete")
    except Exception as exc:
        logger.error("Scheduler: pipeline run failed: %s", exc, exc_info=True)


# ── Public API ────────────────────────────────────────────────────────────────

def apply_schedule(schedule: dict) -> None:
    """
    Update the running BackgroundScheduler to match *schedule*.

    Called on startup (after init_scheduler) and whenever the user saves
    new schedule settings via the dashboard.
    """
    global _scheduler
    if _scheduler is None:
        return

    try:
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler not installed; scheduling disabled")
        return

    # Remove the existing pipeline job (ignore if missing)
    try:
        _scheduler.remove_job("pipeline_run")
    except Exception:
        pass

    pipeline_entries = schedule.get("pipeline", [])
    for entry in pipeline_entries:
        if not entry.get("enabled"):
            continue

        day_of_week, hour, minute = _parse_schedule_entry(entry)
        if hour == -1:
            logger.info("Scheduler: no scheduled job (manual-only mode)")
            continue

        try:
            if day_of_week:
                trigger = CronTrigger(
                    day_of_week=day_of_week,
                    hour=hour,
                    minute=minute,
                    timezone="Asia/Manila",
                )
                label = f"every {day_of_week} at {hour:02d}:{minute:02d} PHT"
            else:
                trigger = CronTrigger(
                    hour=hour,
                    minute=minute,
                    timezone="Asia/Manila",
                )
                label = f"daily at {hour:02d}:{minute:02d} PHT"

            _scheduler.add_job(
                _run_pipeline_job,
                trigger,
                id="pipeline_run",
                replace_existing=True,
            )
            logger.info("Scheduler: pipeline job scheduled %s", label)
        except Exception as exc:
            logger.error("Scheduler: failed to add job: %s", exc, exc_info=True)

        break  # Only one pipeline schedule entry is active at a time


def init_scheduler() -> None:
    """
    Start the BackgroundScheduler and apply saved schedule settings.

    Safe to call multiple times; silently skips if already running.
    Skipped automatically on Vercel (serverless, no persistent process).
    """
    import os
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        return

    # Vercel serverless — no persistent process, scheduler won't fire reliably
    if os.environ.get("VERCEL"):
        logger.info("Scheduler: disabled on Vercel (serverless)")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler not installed; install APScheduler to enable scheduling")
        return

    try:
        import pytz  # noqa: F401  — required by APScheduler for timezone support
    except ImportError:
        logger.warning("pytz not installed; timezone-aware scheduling disabled")

    _scheduler = BackgroundScheduler()
    _scheduler.start()
    logger.info("Scheduler: BackgroundScheduler started")

    # Apply any saved schedule
    settings_file = Path(".settings.json")
    if settings_file.exists():
        try:
            with open(settings_file, encoding="utf-8") as f:
                settings = json.load(f)
            saved_schedule = settings.get("schedule", {})
            if saved_schedule:
                apply_schedule(saved_schedule)
        except Exception as exc:
            logger.warning("Scheduler: could not load saved schedule: %s", exc)
