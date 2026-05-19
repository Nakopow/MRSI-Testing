"""
AI-powered content processing module using Google Gemini.

This module provides functionality for:
    - Initializing the Gemini API client
    - Generating topic-specific summaries
    - Creating unified daily digests
    - Processing articles with AI

Usage:
    >>> from summarizer import generate_daily_digest
    >>> articles = {"ai": [{"title": "...", "body": "..."}]}
    >>> digest = generate_daily_digest(articles)

Environment Variables:
    GEMINI_API_KEY: Google Gemini API key (required)

Configuration:
    All settings are centralized in src.config module
    Prompts are loaded from prompts_config.json
"""

import os
import time
import threading
from dotenv import load_dotenv
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import json

load_dotenv()

# Module-level flag to track if Gemini has been initialized
_gemini_initialized = False
_gemini_lock = threading.Lock()
_gemini_client = None
_gemini_api_keys: Optional[List[str]] = None
_gemini_key_index: int = 0
_gemini_key_label: Optional[str] = None


def _make_genai_client(api_key: str):
    """
    google.generativeai is deprecated; use google-genai.
    Support both import styles for compatibility across versions.
    """
    import importlib.util

    try:
        from google import genai  # type: ignore
    except Exception as e:
        fallback_ok = importlib.util.find_spec("google.genai") is not None
        if fallback_ok:  # pragma: no cover
            import google.genai as genai  # type: ignore
        else:
            raise ImportError(
                "Missing Gemini client library. Install `google-genai` into the active environment "
                "and remove the conflicting `google` package if present:\n"
                "  python -m pip install google-genai\n"
                "  python -m pip uninstall -y google\n"
            ) from e

    return genai.Client(api_key=api_key)


def _response_text(resp) -> str:
    # google-genai exposes a convenience .text in most cases.
    text = getattr(resp, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    # Fallback extraction for older/alternate response shapes.
    try:  # pragma: no cover
        return resp.candidates[0].content.parts[0].text
    except Exception:
        return str(resp)


def _project_root() -> Path:
    # summarizer.py lives in the project root in this repo layout.
    return Path(__file__).resolve().parent


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
        return value[1:-1].strip()
    return value


def _looks_like_gemini_api_key(value: str) -> bool:
    # AI Studio API keys are typically of the form "AIza..." but we keep this permissive.
    v = value.strip()
    if not v:
        return False
    if v.lower().startswith("your_") or v.lower().endswith("_here"):
        return False
    # Basic sanity: avoid obvious non-keys without rejecting valid-but-unusual formats.
    return len(v) >= 20


def _read_dotenv_multi_values(dotenv_path: Path, key: str) -> List[str]:
    """
    Read *all* occurrences of KEY=... from a .env file (python-dotenv keeps only one).
    """
    if not dotenv_path.exists():
        return []

    values: List[str] = []
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() != key:
            continue
        v = _strip_quotes(v)
        if v:
            values.append(v)
    return values


def _split_multi_value(value: str) -> List[str]:
    # Support comma-separated env values: GEMINI_API_KEY=key1,key2,key3
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]


def _load_gemini_api_keys() -> List[str]:
    """
    Load Gemini API keys from:
      1) explicit environment variable (may be comma-separated)
      2) all GEMINI_API_KEY lines in .env (in order)
    """
    keys: List[str] = []

    env_val = os.environ.get("GEMINI_API_KEY")
    if env_val:
        keys.extend(_split_multi_value(env_val))

    keys.extend(_read_dotenv_multi_values(_project_root() / ".env", "GEMINI_API_KEY"))

    # De-duplicate while preserving order
    deduped: List[str] = []
    seen = set()
    for k in keys:
        k = k.strip()
        if k in seen:
            continue
        if not _looks_like_gemini_api_key(k):
            continue
        seen.add(k)
        deduped.append(k)

    return deduped


def _is_retryable_key_error(exc: Exception) -> bool:
    msg = str(exc)
    retry_markers = (
        "API_KEY_INVALID",
        "API key not valid",
        "RESOURCE_EXHAUSTED",
        "429",
        "Too Many Requests",
        "rate limit",
        "quota",
    )
    return any(m in msg for m in retry_markers)


def _is_service_overload_error(exc: Exception) -> bool:
    msg = str(exc).upper()
    overload_markers = (
        "503",
        "UNAVAILABLE",
        "SERVICE UNAVAILABLE",
        "HIGH DEMAND",
    )
    return any(m in msg for m in overload_markers)

# Import config for centralized settings
from src.config import (
    TOPICS,
    TOPIC_DISPLAY_NAMES,
    GEMINI_MODEL,
    DIGEST_FILE,
    ARTICLE_FILES,
    SUMMARY_FILES,
    PROMPTS_PATH,
)

def init_gemini():
    """Initialize the Gemini API client."""
    global _gemini_initialized, _gemini_client, _gemini_api_keys, _gemini_key_index, _gemini_key_label
    if _gemini_initialized:
        return
    
    with _gemini_lock:
        # Double-check after acquiring lock
        if _gemini_initialized:
            return
        
        _gemini_api_keys = _load_gemini_api_keys()
        if not _gemini_api_keys:
            raise ValueError(
                "No Gemini API key found. Set GEMINI_API_KEY in the environment or add one or more "
                "GEMINI_API_KEY=... lines to .env."
            )

        _gemini_key_index = 0
        _gemini_key_label = f"key {_gemini_key_index + 1}/{len(_gemini_api_keys)}"
        _gemini_client = _make_genai_client(_gemini_api_keys[_gemini_key_index])
        _gemini_initialized = True


def _rotate_gemini_key() -> bool:
    """
    Rotate to the next available key and re-initialize the client.
    Returns True if rotated, False if no other key exists.
    """
    global _gemini_client, _gemini_api_keys, _gemini_key_index, _gemini_key_label
    if not _gemini_api_keys or len(_gemini_api_keys) <= 1:
        return False

    _gemini_key_index = (_gemini_key_index + 1) % len(_gemini_api_keys)
    _gemini_key_label = f"key {_gemini_key_index + 1}/{len(_gemini_api_keys)}"
    _gemini_client = _make_genai_client(_gemini_api_keys[_gemini_key_index])
    return True

def summarize_from_file(topic: str, custom_prompt: str = None) -> str:
    """Read articles from file and use Gemini to create a summary."""
    filename = f"{topic}_articles.txt"
    
    try:
        with open(filename, "r", encoding="utf-8") as f:
            articles_text = f.read()
    except FileNotFoundError:
        return f"No {filename} found."
    
    if not articles_text.strip():
        return f"No {topic} articles found in {filename}."
    
    if custom_prompt:
        prompt = custom_prompt.format(topic=topic.upper(), articles=articles_text)
    else:
        return f"No custom prompt found for {topic}"
    
    try:
        return call_gemini_directly(prompt)
    except Exception as e:
        print(f"Error calling Gemini for summary: {e}")
        return f"Failed to summarize {topic} articles."

def generate_topic_summary(topic: str, custom_prompt: str = None) -> str:
    """Generate a complete summary for a single topic using prompts_config.json."""
    init_gemini()
    
    # Load prompt from config file if no custom prompt provided
    if not custom_prompt:
        try:
            with open("prompts_config.json", "r", encoding="utf-8") as f:
                prompts_config = json.load(f)
            custom_prompt = prompts_config.get(topic, {}).get("prompt")
        except FileNotFoundError:
            print(f"prompts_config.json not found, using default for {topic}")
            return f"Failed to load prompts for {topic}"
    
    print(f"Generating summary for {topic}...") 
    summary = summarize_from_file(topic, custom_prompt)
    
    return summary

def generate_separate_summaries(articles_by_topic: dict, today_date: str):
    """Generate separate summaries for each topic from saved article files."""
    with open("prompts_config.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)
    summaries = {}
    
    for topic in TOPICS:
        if topic not in articles_by_topic or not articles_by_topic[topic]:
            print(f"⚠️ No {topic} articles")
            continue

        articles = articles_by_topic[topic][:5]  # Top 5
        sources = "\n".join([
        f"""SOURCE {i+1}
        Title: {art['title']}
        Date: {art['published']}
        Content: {art['body'][:800]}
        """
    for i, art in enumerate(articles)
])

        
        prompt = prompts[topic]["prompt"].format(today_date=today_date)
        full_prompt = prompt + f"\n\nSources:\n{sources}"
        
        # Use your existing summarize_from_file logic but with articles
        summary = call_gemini_directly(full_prompt)  # See below
        
        summaries[topic] = summary
        with open(f"{topic}_summary.txt", "w") as f:
            f.write(summary)
        print(f"✅ {topic} summary saved")
    
    return summaries

def call_gemini_directly(prompt: str) -> str:
    init_gemini()

    assert _gemini_api_keys is not None  # for type checkers
    attempts = max(1, len(_gemini_api_keys))
    per_key_service_retries = 3
    base_backoff_seconds = 2
    last_exc: Optional[Exception] = None

    for _ in range(attempts):
        service_attempts = 0

        while True:
            try:
                response = _gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                return _response_text(response)
            except Exception as e:
                last_exc = e

                if _is_service_overload_error(e):
                    service_attempts += 1
                    if service_attempts <= per_key_service_retries:
                        wait_seconds = base_backoff_seconds * service_attempts
                        label = _gemini_key_label or "current key"
                        print(
                            f"Gemini temporarily unavailable on {label} "
                            f"({service_attempts}/{per_key_service_retries}); retrying in {wait_seconds}s..."
                        )
                        time.sleep(wait_seconds)
                        continue

                    prev_label = _gemini_key_label or "current key"
                    if not _rotate_gemini_key():
                        break
                    next_label = _gemini_key_label or "next key"
                    print(
                        f"Gemini stayed unavailable on {prev_label} after "
                        f"{per_key_service_retries} retries; rotating to {next_label}..."
                    )
                    break

                if not _is_retryable_key_error(e):
                    raise

                prev_label = _gemini_key_label or "current key"
                if not _rotate_gemini_key():
                    break
                next_label = _gemini_key_label or "next key"
                print(f"Gemini request failed with {prev_label}; rotating to {next_label}...")
                break

    label = _gemini_key_label or "current key"
    raise RuntimeError(f"Gemini request failed after trying {attempts} key(s) (last: {label}): {last_exc}") from last_exc


def generate_daily_digest(articles_by_topic: dict) -> str:
    """
    Generate a complete daily digest combining all topics.
    
    This is the main function called by main.py for the automated pipeline.
    
    Args:
        articles_by_topic: Dictionary mapping topics to lists of article dictionaries
        
    Returns:
        Complete digest string ready for output
    """
    init_gemini()
    
    # Get today's date
    today_date = datetime.now().strftime('%B %d, %Y')
    
    # Load prompts
    try:
        with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
            prompts_config = json.load(f)
    except FileNotFoundError:
        print(f"Error: {PROMPTS_PATH} not found")
        return "Error: prompts_config.json not found"
    
    digest_parts = []
    
    # Add header
    digest_parts.append(f"# Daily Technology Digest\n")
    digest_parts.append(f"## {today_date}\n")
    digest_parts.append("=" * 80 + "\n\n")
    
    # Generate summary for each topic
    for topic in TOPICS:
        if topic not in articles_by_topic or not articles_by_topic[topic]:
            print(f"⚠️ No {topic} articles found, skipping...")
            continue
        
        display_name = TOPIC_DISPLAY_NAMES.get(topic, topic.upper())
        print(f"Generating {display_name} summary...")
        
        # Get top 5 articles for this topic
        articles = articles_by_topic[topic][:5]
        
        # Build sources list
        sources = "\n".join([
            f"SOURCE {i+1}: {art['title']} - {art['published']}"
            for i, art in enumerate(articles)
        ])
        
        # Get prompt template
        prompt_template = prompts_config.get(topic, {}).get("prompt", "")
        if not prompt_template:
            print(f"Warning: No prompt found for {topic}")
            continue
        
        # Format prompt with today's date
        full_prompt = prompt_template.format(today_date=today_date)
        full_prompt += f"\n\n{sources}"
        
        try:
            # Call Gemini
            summary = call_gemini_directly(full_prompt)
            
            # Add to digest
            digest_parts.append(f"\n{'=' * 80}\n")
            digest_parts.append(f"## {display_name.upper()}\n")
            digest_parts.append(f"{'=' * 80}\n\n")
            digest_parts.append(summary)
            digest_parts.append("\n")
            
            # Save individual topic summary
            with open(SUMMARY_FILES[topic], "w", encoding="utf-8") as f:
                f.write(summary)
            print(f"✅ {topic} summary saved")
            
        except Exception as e:
            print(f"Error generating {topic} summary: {e}")
            digest_parts.append(f"\n## {display_name.upper()}\n")
            digest_parts.append(f"Error: Failed to generate summary\n")
    
    # Create summary files for topics with no articles
    for topic in TOPICS:
        if topic not in articles_by_topic or not articles_by_topic[topic]:
            display_name = TOPIC_DISPLAY_NAMES.get(topic, topic.upper())
            no_articles_msg = f"No {display_name} articles found for today.\n"
            with open(SUMMARY_FILES[topic], "w", encoding="utf-8") as f:
                f.write(no_articles_msg)
            print(f"✅ Created {topic}_summary.txt (no articles found)")
    
    # Combine all parts
    final_digest = "\n".join(digest_parts)
    
    return final_digest
