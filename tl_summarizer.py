"""
tl_summarizer.py
Reads today's Daily Insight output.txt per topic, calls Gemini to generate
the Thought Leadership Content Pack, then generates the 5 platform images
using the configured image backend (default: Hugging Face Inference API).

Saves one JSON per topic: tl_output_{topic}_{date}.json

By default filenames omit the date so each run replaces the previous output
per topic: tl_output_{topic}.json. Use --dated-filenames to keep the old behavior.

Usage:
    python tl_summarizer.py <GEMINI_API_KEY>

    Or set them in .env using duplicate lines (one per account):
    GEMINI_API_KEY=key1
    GEMINI_API_KEY=key2
    GEMINI_API_KEY=key3

GEMINI_API_KEY supports rotation. Gemini rotates on any API error.
HF_API_TOKEN supports rotation for Hugging Face image generation.

FIXES APPLIED (Mar 16, 2026):
  1. FORMAT field now extracted and stored in each piece dict.
  2. extract_field() fixed — empty next_labels no longer breaks the regex lookahead.
  3. Instagram platform/angle regex fixed — greedy capture no longer swallows the angle.
  4. Gemini key rotation added — multiple GEMINI_API_KEY lines in .env, rotates on error.

ENHANCEMENTS (Mar 17, 2026):
  5. Image generation style overhaul — bold, attention-grabbing aesthetic with
     configurable IMAGE_STYLE_PRESET. Change the preset constant below to switch
     the global visual mood for all generated images.
"""

import os, sys, json, re, base64, time, argparse
import urllib.request
import urllib.error
from collections import Counter
from datetime import datetime
from typing import Optional

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROMPTS_FILE = os.path.join(SCRIPT_DIR, "tl_prompts_config.json")
OUTPUT_TXT   = os.path.join(SCRIPT_DIR, "output.txt")

# ─────────────────────────────────────────────────────────────────────────────
# IMAGE STYLE PRESET
# Change this single constant to restyle ALL generated images globally.
#
# Available presets:
#   "bold"        — high-contrast, vivid colors, punchy and thumb-stopping
#   "cinematic"   — dark moody background, deep purple/navy, cinematic lighting
#   "minimal"     — clean white/light background, flat design, editorial feel
#   "neon"        — neon-lit dark scene, cyberpunk glow, electric accents
#   "corporate"   — professional, polished, blue tones, boardroom aesthetic
#
# You can also set this via environment variable IMAGE_STYLE_PRESET.
# ─────────────────────────────────────────────────────────────────────────────
IMAGE_STYLE_PRESET = os.environ.get("IMAGE_STYLE_PRESET", "bold")

_IMAGE_STYLE_SUFFIXES = {
    "bold": (
        "Ultra-bold graphic design, extreme high contrast, vivid saturated colors, "
        "eye-catching composition, striking visual hierarchy, "
        "thumb-stopping social media aesthetic, sharp focus, "
        "allow a single short context label only (1–2 words max), large clean typography, "
        "no additional words, no small print, no sentences, no paragraphs, "
        "no watermark, no logo, "
        "photorealistic or hyper-stylized illustration, strong focal point, 4K quality."
    ),
    "cinematic": (
        "Dark background, cinematic professional lighting, deep purple and navy tones, "
        "corporate strategic mood, sharp focus, photorealistic, "
        "allow a single short context label only (1–2 words max), large clean typography, "
        "no additional words, no small print, no sentences, no paragraphs, "
        "no watermark, no logo."
    ),
    "minimal": (
        "Clean minimal design, white or very light background, flat editorial aesthetic, "
        "generous whitespace, single bold focal element, "
        "high-end magazine look, "
        "allow a single short context label only (1–2 words max), subtle clean typography, "
        "no additional words, no small print, no sentences, no paragraphs, "
        "no watermark, no logo, 4K quality."
    ),
    "neon": (
        "Neon-lit dark scene, cyberpunk glow, electric blue and magenta accents, "
        "futuristic tech atmosphere, lens flare, deep shadow, ultra-vivid, "
        "allow a single short context label only (1–2 words max), large clean typography, "
        "no additional words, no small print, no sentences, no paragraphs, "
        "no watermark, no logo, "
        "sharp focus, 4K quality."
    ),
    "corporate": (
        "Professional corporate photography style, polished blue and white tones, "
        "clean boardroom or modern office aesthetic, confident mood, "
        "high production value, "
        "allow a single short context label only (1–2 words max), clean typography, "
        "no additional words, no small print, no sentences, no paragraphs, "
        "no watermark, no logo, 4K quality."
    ),
}


def _style_suffix():
    """Return the style suffix string for the active IMAGE_STYLE_PRESET."""
    preset = IMAGE_STYLE_PRESET.lower()
    suffix = _IMAGE_STYLE_SUFFIXES.get(preset)
    if not suffix:
        print(f"  [warn] Unknown IMAGE_STYLE_PRESET '{preset}' — falling back to 'bold'.")
        suffix = _IMAGE_STYLE_SUFFIXES["bold"]
    return suffix


# ── Load .env file if present ─────────────────────────────────────────────────
_MULTI_VALUE_KEYS = {"GEMINI_API_KEY", "HF_API_TOKEN"}

def _load_env():
    env_path = os.path.join(SCRIPT_DIR, ".env")
    if not os.path.exists(env_path):
        return

    collected: dict[str, list[str]] = {}
    with open(env_path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and val:
                collected.setdefault(key, [])
                collected[key].append(val)

    for key, values in collected.items():
        if key in os.environ:
            continue
        if key in _MULTI_VALUE_KEYS:
            os.environ[key] = ",".join(values)
        else:
            os.environ[key] = values[0]

_load_env()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
# NOTE: `imagen-3.0-fast-generate-001` is a common Vertex AI Imagen model id but
# is not always available on the Gemini API endpoint used by `google-genai`.
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL") or "imagen-4.0-fast-generate-001"
IMAGE_BACKEND = (os.environ.get("IMAGE_BACKEND") or "huggingface").strip().lower()
HF_IMAGE_MODEL = os.environ.get("HF_IMAGE_MODEL") or "runwayml/stable-diffusion-v1-5"
HF_INFERENCE_ENDPOINT = os.environ.get("HF_INFERENCE_ENDPOINT") or "https://api-inference.huggingface.co/models"


def _ensure_ssl_ca_bundle():
    """
    Avoid slow/hanging SSL verification setup on some Windows/Python setups by
    explicitly pointing OpenSSL to a known-good CA bundle (certifi), when
    no valid CA env var is already configured.
    """
    try:
        import certifi  # type: ignore
    except Exception:
        return

    cafile = getattr(certifi, "where", None)
    cafile = cafile() if callable(cafile) else None
    if not cafile or not os.path.exists(cafile):
        return

    force = os.environ.get("TL_FORCE_CERTIFI_SSL") in ("1", "true", "TRUE", "yes", "YES")
    current = os.environ.get("SSL_CERT_FILE")
    if not force and current and os.path.exists(current):
        return

    os.environ["SSL_CERT_FILE"] = cafile
    os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
    if os.environ.get("TL_SUMMARIZER_DEBUG_SSL") in ("1", "true", "TRUE", "yes", "YES"):
        print(f"Note: SSL_CERT_FILE set to certifi bundle: {cafile}")


def _image_model_candidates() -> list[str]:
    """
    Returns a de-duplicated list of image model ids to try, in order.
    """
    preferred = (globals().get("GEMINI_IMAGE_MODEL") or "").strip()
    candidates = [
        preferred,
        # Common Gemini API Imagen model ids (keep most-likely first).
        "imagen-4.0-fast-generate-001",
        "imagen-4.0-generate-001",
        "imagen-3.0-generate-002",
        "imagen-3.0-generate-001",
    ]

    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if not c:
            continue
        if c in seen:
            continue
        seen.add(c)
        ordered.append(c)
    return ordered


_ensure_ssl_ca_bundle()


class HfApiError(RuntimeError):
    def __init__(self, status_code: int, message: str, body: Optional[str] = None):
        super().__init__(f"HF {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.body = body


def _hf_model_candidates() -> list[str]:
    preferred = (globals().get("HF_IMAGE_MODEL") or "").strip()
    candidates = [
        preferred,
        # Keep a couple of common fallbacks (may be gated depending on account/model).
        "runwayml/stable-diffusion-v1-5",
        "stabilityai/stable-diffusion-2-1",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for c in candidates:
        if not c:
            continue
        if c in seen:
            continue
        seen.add(c)
        ordered.append(c)
    return ordered


def _hf_build_url(model_id: str) -> str:
    base = (globals().get("HF_INFERENCE_ENDPOINT") or "").rstrip("/")
    return f"{base}/{model_id}"


def _hf_decode_error_body(body_bytes: bytes) -> tuple[str, Optional[float]]:
    """
    Hugging Face inference errors are typically JSON:
      {"error": "...", "estimated_time": 12.3}
    """
    try:
        s = body_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        return ("(unable to decode error body)", None)

    try:
        j = json.loads(s) if s else {}
        msg = j.get("error") or j.get("message") or s
        est = j.get("estimated_time")
        try:
            est = float(est) if est is not None else None
        except Exception:
            est = None
        return (str(msg), est)
    except Exception:
        return (s or "(empty error body)", None)


def _hf_post_image(model_id: str, prompt_text: str, token: str, width: int, height: int,
                   timeout_s: int = 45) -> bytes:
    url = _hf_build_url(model_id)
    payload = {
        "inputs": prompt_text,
        "parameters": {
            "width": width,
            "height": height,
        },
        "options": {
            # If the model is still loading, we prefer a deterministic retry loop below.
            "wait_for_model": False,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/*",
        "User-Agent": "tl_summarizer/1.0",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            ct = (resp.headers.get("Content-Type") or "").lower()
            body = resp.read()
            if ct.startswith("image/"):
                return body
            # Sometimes HF returns JSON even on 200 if something is off.
            msg, est = _hf_decode_error_body(body)
            raise HfApiError(getattr(resp, "status", 200), msg, body.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        msg, est = _hf_decode_error_body(body)
        if e.code == 503 and est:
            # Let caller decide whether/how long to wait; surface est in message.
            raise HfApiError(e.code, f"{msg} (estimated_time={est}s)", body.decode("utf-8", errors="replace"))
        raise HfApiError(e.code, msg, body.decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"HF network error: {e}") from e


def _hf_generate_image_bytes(prompt_text: str, tokens: list[str], aspect_ratio: str) -> Optional[bytes]:
    global _IMAGES_DISABLED_REASON

    if _IMAGES_DISABLED_REASON:
        return None

    if not tokens:
        _IMAGES_DISABLED_REASON = "No Hugging Face token(s) provided (HF_API_TOKEN)."
        return None

    width, height = ASPECT_DIMS.get(aspect_ratio, (1024, 1024))
    enhanced = (
        f"{prompt_text} {_style_suffix()} "
        f"(Target size approx {width}x{height}, aspect {aspect_ratio}.)"
    ).strip()

    model_candidates = _hf_model_candidates()
    last_error: Optional[Exception] = None

    for idx, token in enumerate(tokens):
        token_label = f"token {idx + 1}/{len(tokens)}"
        rotate_token = False

        for model_id in model_candidates:
            # Small bounded retry for "model loading" (503) cases.
            for attempt in range(1, 4):
                try:
                    img = _hf_post_image(model_id, enhanced, token, width, height, timeout_s=45)
                    if idx > 0:
                        print(f"      [hf-img] Success with {token_label}.")
                    if model_id != HF_IMAGE_MODEL:
                        print(f"      [hf-img] Using fallback HF model: {model_id}")
                    return img
                except HfApiError as e:
                    last_error = e
                    # Token issues / quota -> rotate token.
                    if e.status_code in (401, 403, 429):
                        print(f"      [hf-img] {token_label} rejected or rate-limited — rotating to next token...")
                        rotate_token = True
                        break
                    # Model still loading (503). Try a short sleep then retry; if it keeps
                    # happening, rotate token to avoid stalling the whole run.
                    if e.status_code == 503:
                        if attempt < 3:
                            time.sleep(2)
                            continue
                        rotate_token = True
                        break
                    # Model gated / invalid params; try next model.
                    if e.status_code in (400, 404, 422):
                        break
                    # Unknown HF error: rotate token and continue best-effort.
                    rotate_token = True
                    break
                except Exception as e:
                    last_error = e
                    rotate_token = True
                    break

            if rotate_token:
                break

        if rotate_token:
            continue

    print(f"      [hf-img] All HF tokens/models failed — placeholder will be used. Last error: {last_error}")
    return None

TOPIC_HEADERS = {
    "ai":            "ARTIFICIAL INTELLIGENCE",
    "cybersecurity": "CYBERSECURITY",
    "web3":          "WEB3 / BLOCKCHAIN",
}
TOPIC_DISPLAY = {
    "ai":            "AI",
    "cybersecurity": "CyberSec",
    "web3":          "Web3",
}

# ── Extract topic briefing from output.txt ────────────────────────────────────

def extract_topic_text(output_txt_path, topic_key):
    with open(output_txt_path, encoding="utf-8") as f:
        content = f.read()
    header = TOPIC_HEADERS[topic_key]
    pattern = re.compile(
        r"^\s*##\s*" + re.escape(header) + r"\s*$" + r"(.*?)(?=^\s*##\s+|\Z)",
        re.DOTALL | re.IGNORECASE | re.MULTILINE
    )
    m = pattern.search(content)
    if not m:
        return None

    section = m.group(1).strip()
    if not section:
        return None

    if re.fullmatch(r"Error:\s*Failed to generate summary\s*", section, re.IGNORECASE):
        return None

    return section

# ── Parse Gemini output into structured fields ────────────────────────────────

def parse_tl_output(raw_text):
    result = {"editorial_note": "", "pieces": []}

    en_m = re.search(r"EDITORIAL NOTE\s*\n(.*?)(?=\n0[12345]\s*[·\-])", raw_text, re.DOTALL)
    if en_m:
        result["editorial_note"] = en_m.group(1).strip()

    piece_pattern = re.compile(
        r"^(0[1-5])\s*[-]\s*"
        r"(LinkedIn|YouTube\s*/\s*Video Script|Instagram Carousel|Facebook|TikTok)"
        r"\s*[-]\s*([^\n]+)",
        re.IGNORECASE | re.MULTILINE
    )

    pieces_raw = []
    for m in piece_pattern.finditer(raw_text):
        pieces_raw.append((
            m.start(),
            m.group(1),
            m.group(2).strip(),
            m.group(3).strip(),
        ))

    ALL_LABELS = [
        "OBJECTIVE", "FORMAT", "IMAGE GUIDANCE", "COPY", "SCRIPT",
        "SLIDES", "CAPTION", "POSTING NOTES", "PRODUCTION NOTES",
    ]

    for i, (start, num, platform, angle) in enumerate(pieces_raw):
        end   = pieces_raw[i + 1][0] if i + 1 < len(pieces_raw) else len(raw_text)
        block = raw_text[start:end]

        def extract_field(label, next_labels, blk=block):
            if next_labels:
                lookahead = "|".join(re.escape(l) for l in next_labels)
                pat = label + r"\s*\n(.*?)(?=" + lookahead + r"|\Z)"
            else:
                pat = label + r"\s*\n(.*?)(?=\Z)"
            m = re.search(pat, blk, re.DOTALL)
            return m.group(1).strip() if m else ""

        fmt           = extract_field("FORMAT",         ALL_LABELS[2:])
        objective     = extract_field("OBJECTIVE",      ALL_LABELS[1:])
        image_guid    = extract_field("IMAGE GUIDANCE", ALL_LABELS[3:])

        posting_notes = (
            extract_field("POSTING NOTES",    ["PRODUCTION NOTES"])
            or extract_field("PRODUCTION NOTES", ["POSTING NOTES"])
            or extract_field("POSTING NOTES",    [])
            or extract_field("PRODUCTION NOTES", [])
        )

        piece = {
            "number":         num,
            "platform":       platform,
            "angle":          angle,
            "format":         fmt,
            "objective":      objective,
            "image_guidance": image_guid,
            "posting_notes":  posting_notes,
            "copy":           "",
            "script":         "",
            "slides":         [],
            "caption":        "",
        }

        plat_lower = platform.lower()

        if "instagram" in plat_lower:
            slides_raw       = extract_field("SLIDES",  ["CAPTION", "POSTING NOTES", "PRODUCTION NOTES"])
            piece["slides"]  = _parse_slides(slides_raw)
            piece["caption"] = extract_field("CAPTION", ["POSTING NOTES", "PRODUCTION NOTES"])

        elif "youtube" in plat_lower or "video" in plat_lower:
            piece["script"] = extract_field("SCRIPT", ["POSTING NOTES", "PRODUCTION NOTES"])

        elif "tiktok" in plat_lower:
            piece["script"]  = extract_field("SCRIPT",  ["CAPTION", "POSTING NOTES", "PRODUCTION NOTES"])
            piece["caption"] = extract_field("CAPTION", ["POSTING NOTES", "PRODUCTION NOTES"])

        else:
            piece["copy"] = extract_field("COPY", ["POSTING NOTES", "PRODUCTION NOTES"])

        result["pieces"].append(piece)

    return result


def _parse_slides(slides_raw):
    slides, current = [], []
    for line in slides_raw.split("\n"):
        line = line.strip()
        if re.match(r"Slide\s*\d+", line, re.IGNORECASE):
            if current:
                slides.append("\n".join(current))
                current = []
            after = re.sub(r"Slide\s*\d+\s*:?\s*", "", line, flags=re.IGNORECASE).strip()
            if after:
                current.append(after)
        elif line:
            current.append(line)
    if current:
        slides.append("\n".join(current))
    return slides

# ── Gemini call ───────────────────────────────────────────────────────────────

def _parse_gemini_keys(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        keys = raw
    else:
        keys = [k.strip() for k in str(raw).split(",")]
    return [k for k in keys if k]


def _import_genai():
    import importlib.util

    try:
        from google import genai  # type: ignore
        return genai
    except Exception as e:
        fallback_ok = importlib.util.find_spec("google.genai") is not None
        if fallback_ok:
            import google.genai as genai  # type: ignore
            return genai
        raise ImportError(
            "Missing Gemini client library. Install `google-genai` into the same Python "
            "environment you're running, and remove the conflicting `google` package if present:\n"
            "  python -m pip install google-genai\n"
            "  python -m pip uninstall -y google\n"
        ) from e


def call_gemini(prompt_text, api_key):
    genai = _import_genai()

    keys = _parse_gemini_keys(api_key)
    if not keys:
        raise ValueError("No Gemini API key provided.")

    last_error = None
    for idx, key in enumerate(keys):
        key_label = f"key {idx + 1}/{len(keys)}"
        try:
            client = genai.Client(api_key=key)
            resp   = client.models.generate_content(model=GEMINI_MODEL, contents=prompt_text)
            text   = getattr(resp, "text", None)
            if isinstance(text, str) and text.strip():
                if idx > 0:
                    print(f"    [gemini] Success with {key_label}.")
                return text.strip()
            try:
                result = resp.candidates[0].content.parts[0].text.strip()
                if idx > 0:
                    print(f"    [gemini] Success with {key_label}.")
                return result
            except Exception:
                return str(resp).strip()
        except Exception as e:
            last_error = e
            err_str = str(e)
            if any(code in err_str for code in ["INVALID_ARGUMENT", "API_KEY_INVALID",
                                                  "PERMISSION_DENIED", "401", "403", "400"]):
                print(f"    [gemini] {key_label} invalid or rejected — rotating to next key...")
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                print(f"    [gemini] {key_label} quota exhausted — rotating to next key...")
            else:
                print(f"    [gemini] {key_label} error: {e} — rotating to next key...")

    raise RuntimeError(f"All Gemini keys failed. Last error: {last_error}")

# ── Gemini image generation ───────────────────────────────────────────────────

def _is_gemini_invalid_key_error(err_str):
    return any(
        code in err_str
        for code in ["INVALID_ARGUMENT", "API_KEY_INVALID", "PERMISSION_DENIED", "401", "403", "400"]
    )


def _is_gemini_quota_error(err_str):
    return "429" in err_str or "RESOURCE_EXHAUSTED" in err_str


def _is_gemini_service_overload_error(err_str):
    upper = err_str.upper()
    return (
        "503" in err_str
        or "UNAVAILABLE" in upper
        or "SERVICE UNAVAILABLE" in upper
        or "HIGH DEMAND" in upper
    )


def call_gemini_resilient(prompt_text, api_key, per_key_service_retries=3, base_backoff_seconds=2):
    genai = _import_genai()

    keys = _parse_gemini_keys(api_key)
    if not keys:
        raise ValueError("No Gemini API key provided.")

    last_error = None
    for idx, key in enumerate(keys):
        key_label = f"key {idx + 1}/{len(keys)}"
        client = genai.Client(api_key=key)
        service_attempts = 0

        while True:
            try:
                resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt_text)
                text = getattr(resp, "text", None)
                if isinstance(text, str) and text.strip():
                    if idx > 0 or service_attempts > 0:
                        print(f"    [gemini] Success with {key_label}.")
                    return text.strip()
                try:
                    result = resp.candidates[0].content.parts[0].text.strip()
                    if idx > 0 or service_attempts > 0:
                        print(f"    [gemini] Success with {key_label}.")
                    return result
                except Exception:
                    return str(resp).strip()
            except Exception as e:
                last_error = e
                err_str = str(e)

                if _is_gemini_invalid_key_error(err_str):
                    print(f"    [gemini] {key_label} invalid or rejected - rotating to next key...")
                    break

                if _is_gemini_quota_error(err_str):
                    print(f"    [gemini] {key_label} quota exhausted - rotating to next key...")
                    break

                if _is_gemini_service_overload_error(err_str):
                    service_attempts += 1
                    if service_attempts <= per_key_service_retries:
                        wait_seconds = base_backoff_seconds * service_attempts
                        print(
                            f"    [gemini] {key_label} hit temporary service overload "
                            f"({service_attempts}/{per_key_service_retries}) - retrying in {wait_seconds}s..."
                        )
                        time.sleep(wait_seconds)
                        continue

                    print(
                        f"    [gemini] {key_label} still unavailable after "
                        f"{per_key_service_retries} retries - rotating to next key..."
                    )
                    break

                print(f"    [gemini] {key_label} error: {e} - rotating to next key...")
                break

    raise RuntimeError(f"All Gemini keys failed. Last error: {last_error}")


PLATFORM_ASPECT = {
    "linkedin":  "16:9",
    "youtube":   "16:9",
    "instagram": "1:1",
    "facebook":  "16:9",
    "tiktok":    "9:16",
}

ASPECT_DIMS = {
    "16:9": (1024, 576),
    "1:1":  (1024, 1024),
    "9:16": (576,  1024),
}

def _looks_like_base64(s: str) -> bool:
    if not s or len(s) < 32:
        return False
    return s.startswith(("iVBORw0KGgo", "/9j/")) or re.fullmatch(r"[A-Za-z0-9+/=\\s]+", s) is not None


def _b64_to_bytes(s: str) -> Optional[bytes]:
    if not _looks_like_base64(s):
        return None
    try:
        return base64.b64decode(re.sub(r"\\s+", "", s), validate=False)
    except Exception:
        return None


def _extract_first_image_bytes(resp) -> Optional[bytes]:
    """
    Best-effort extraction across google-genai versions/response shapes.
    Returns raw bytes (PNG/JPEG/etc) or None.
    """
    if resp is None:
        return None

    if isinstance(resp, (bytes, bytearray)):
        return bytes(resp)

    if isinstance(resp, str):
        return _b64_to_bytes(resp)

    def get(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    for list_attr in ("generated_images", "images", "data", "outputs"):
        items = get(resp, list_attr)
        if isinstance(items, list) and items:
            for item in items:
                for k in ("image_bytes", "bytes", "data", "png", "jpeg", "content"):
                    val = get(item, k)
                    if isinstance(val, (bytes, bytearray)):
                        return bytes(val)
                    if isinstance(val, str):
                        b = _b64_to_bytes(val)
                        if b:
                            return b
                    if val is not None and not isinstance(val, (str, bytes, bytearray)):
                        for kk in ("image_bytes", "bytes", "data"):
                            vv = get(val, kk)
                            if isinstance(vv, (bytes, bytearray)):
                                return bytes(vv)
                            if isinstance(vv, str):
                                b = _b64_to_bytes(vv)
                                if b:
                                    return b

    candidates = get(resp, "candidates")
    if isinstance(candidates, list) and candidates:
        content = get(candidates[0], "content")
        parts = get(content, "parts") if content is not None else None
        if isinstance(parts, list):
            for part in parts:
                inline = get(part, "inline_data") or get(part, "inlineData")
                data = get(inline, "data") if inline is not None else None
                if isinstance(data, (bytes, bytearray)):
                    return bytes(data)
                if isinstance(data, str):
                    b = _b64_to_bytes(data)
                    if b:
                        return b

    return None


def _genai_generate_image_response(client, model_id: str, prompt_text: str, aspect_ratio: str):
    models = getattr(client, "models", None)
    if models is None:
        raise RuntimeError("Gemini client missing `.models` API.")

    config = {
        "number_of_images": 1,
        "aspect_ratio": aspect_ratio,
    }

    for fn_name in ("generate_images", "generate_image"):
        fn = getattr(models, fn_name, None)
        if not callable(fn):
            continue
        try:
            return fn(model=model_id, prompt=prompt_text, config=config)
        except TypeError:
            try:
                return fn(model=model_id, prompt=prompt_text)
            except TypeError:
                try:
                    return fn(model=model_id, contents=prompt_text, config=config)
                except TypeError:
                    return fn(model=model_id, contents=prompt_text)

    raise RuntimeError(
        "Your installed `google-genai` package doesn't expose an image generation API. "
        "Upgrade it:\n  python -m pip install --upgrade google-genai"
    )


def _is_model_not_found_error(err: Exception) -> bool:
    s = str(err)
    return (
        "NOT_FOUND" in s
        or "404" in s
        or "is not found for API version" in s
        or "not supported for predict" in s
    )


def _is_paid_plan_required_error(err: Exception) -> bool:
    s = str(err).lower()
    return (
        "only available on paid plans" in s
        or "please upgrade your account" in s
        or "upgrade your account" in s
        or "ai.dev/projects" in s
    )


_IMAGES_DISABLED_REASON: Optional[str] = None


def generate_image_gemini(prompt_text, gemini_keys, aspect_ratio="1:1"):
    """
    Generate an image via Gemini image generation.
    Accepts a single key string or a list of keys.
    Rotates to the next key automatically on API error/quota.
    Returns raw image bytes, or None if all keys fail.
    """
    global _IMAGES_DISABLED_REASON
    if _IMAGES_DISABLED_REASON:
        return None

    genai = _import_genai()

    keys = _parse_gemini_keys(gemini_keys)
    if not keys:
        return None

    width, height = ASPECT_DIMS.get(aspect_ratio, (1024, 1024))
    enhanced = (
        f"{prompt_text} {_style_suffix()} "
        f"(Target size approx {width}x{height}, aspect {aspect_ratio}.)"
    ).strip()

    model_candidates = _image_model_candidates()
    last_error = None
    for idx, key in enumerate(keys):
        key_label = f"key {idx + 1}/{len(keys)}"
        try:
            client = genai.Client(api_key=key)
            model_last_error: Optional[Exception] = None
            for model_id in model_candidates:
                try:
                    resp = _genai_generate_image_response(client, model_id, enhanced, aspect_ratio)
                    img_bytes = _extract_first_image_bytes(resp)
                    if img_bytes:
                        if idx > 0:
                            print(f"      [gemini-img] Success with {key_label}.")
                        if model_id != GEMINI_IMAGE_MODEL:
                            print(f"      [gemini-img] Using fallback image model: {model_id}")
                        return img_bytes
                    raise RuntimeError("No image bytes returned by Gemini image generation.")
                except Exception as e:
                    if _is_paid_plan_required_error(e):
                        _IMAGES_DISABLED_REASON = "Gemini Imagen image generation requires a paid plan."
                        print(f"      [gemini-img] {_IMAGES_DISABLED_REASON} Disabling images for the rest of this run.")
                        return None
                    if _is_model_not_found_error(e):
                        model_last_error = e
                        last_error = e
                        continue
                    raise
            if model_last_error is not None:
                raise model_last_error
            raise RuntimeError("No supported Gemini image generation model succeeded.")
        except Exception as e:
            last_error = e
            err_str = str(e)
            if _is_paid_plan_required_error(e):
                _IMAGES_DISABLED_REASON = "Gemini Imagen image generation requires a paid plan."
                print(f"      [gemini-img] {_IMAGES_DISABLED_REASON} Disabling images for the rest of this run.")
                return None
            if any(code in err_str for code in ["API_KEY_INVALID", "PERMISSION_DENIED", "401", "403"]):
                print(f"      [gemini-img] {key_label} invalid or rejected — rotating to next key...")
            elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                print(f"      [gemini-img] {key_label} quota exhausted — rotating to next key...")
            else:
                print(f"      [gemini-img] {key_label} error: {e} — rotating to next key...")

    print(f"      [gemini-img] All Gemini keys failed — placeholder will be used. Last error: {last_error}")
    return None


def generate_image(prompt_text, gemini_keys, aspect_ratio="1:1"):
    """
    Image generation dispatcher.
      - IMAGE_BACKEND=huggingface: uses HF Inference API (HF_API_TOKEN, HF_IMAGE_MODEL)
      - IMAGE_BACKEND=gemini: uses Gemini Imagen (GEMINI_API_KEY, GEMINI_IMAGE_MODEL)
      - IMAGE_BACKEND=none: always returns None (placeholders)
    """
    backend = (globals().get("IMAGE_BACKEND") or "huggingface").strip().lower()
    if backend in ("none", "off", "disabled"):
        return None

    if backend in ("huggingface", "hf"):
        tokens = _parse_gemini_keys(os.environ.get("HF_API_TOKEN"))
        return _hf_generate_image_bytes(prompt_text, tokens, aspect_ratio)

    return generate_image_gemini(prompt_text, gemini_keys, aspect_ratio)


# ── Platform key helper ───────────────────────────────────────────────────────

def _plat_key(platform_str):
    p = platform_str.lower()
    if "linkedin"  in p: return "linkedin"
    if "youtube"   in p or "video" in p: return "youtube"
    if "instagram" in p: return "instagram"
    if "facebook"  in p: return "facebook"
    if "tiktok"    in p: return "tiktok"
    return "linkedin"

# ── Image prompt helpers ───────────────────────────────────────────────────────

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "you",
    "are", "was", "were", "has", "have", "had", "will", "can", "could", "should",
    "about", "than", "then", "when", "what", "where", "why", "how", "who",
    "their", "there", "here", "over", "under", "between", "within", "without",
    "also", "more", "most", "some", "many", "much", "such",
}


def _clean_text_for_keywords(text: str) -> str:
    if not text:
        return ""
    # Remove URLs and collapse whitespace.
    text = re.sub(r"https?://\\S+", " ", text)
    text = text.replace("#", " ").replace("@", " ")
    text = re.sub(r"\\s+", " ", text).strip()
    return text


def _extract_keywords(text: str, max_keywords: int = 12) -> list[str]:
    text = _clean_text_for_keywords(text).lower()
    if not text:
        return []

    words = re.findall(r"[a-z][a-z0-9\\-]{2,}", text)
    words = [w for w in words if len(w) >= 4 and w not in _STOPWORDS]
    if not words:
        return []

    counts = Counter(words)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for (w, _) in ranked[:max_keywords]]


def _piece_content_text(piece: dict) -> str:
    p = (piece.get("platform") or "").lower()
    if "instagram" in p:
        slides = piece.get("slides") or []
        caption = piece.get("caption") or ""
        return "\n".join(slides) + "\n" + caption
    if "youtube" in p or "video" in p:
        return piece.get("script") or ""
    if "tiktok" in p:
        return (piece.get("script") or "") + "\n" + (piece.get("caption") or "")
    # LinkedIn / Facebook / others
    return piece.get("copy") or ""


def _platform_visual_hint(pk: str) -> str:
    if pk == "youtube":
        return "YouTube thumbnail style: bold composition, single clear subject, high contrast, dramatic lighting."
    if pk == "tiktok":
        return "Vertical social post style: dynamic action, strong focal subject, energetic lighting."
    if pk == "linkedin":
        return "Professional editorial style: clean modern business/tech visual, credible and polished."
    if pk == "facebook":
        return "Social feed style: vibrant, relatable, high-impact visual with clear focal subject."
    if pk == "instagram":
        return "Instagram square post style: visually striking, modern, cohesive, strong focal subject."
    return "Modern tech editorial style: clean, high-impact visual with a clear focal subject."


def _build_image_prompt_for_piece(piece: dict) -> str:
    base = (piece.get("image_guidance") or "").strip()
    angle = (piece.get("angle") or "").strip()
    objective = (piece.get("objective") or "").strip()
    fmt = (piece.get("format") or "").strip()
    platform = (piece.get("platform") or "").strip()
    pk = _plat_key(platform)

    keywords = _extract_keywords(_piece_content_text(piece))

    parts: list[str] = []
    if base:
        parts.append(base.rstrip("."))
    if angle:
        parts.append(f"Visual concept: {angle}.")
    if objective:
        parts.append(f"Goal: {objective}.")
    if fmt:
        parts.append(f"Post format: {fmt}.")
    if keywords:
        parts.append("Key themes: " + ", ".join(keywords) + ".")
    if platform:
        parts.append(f"Make it clearly relevant to this {platform} post.")

    parts.append(_platform_visual_hint(pk))
    parts.append(
        "Include at most one short context label (1–2 words max), "
        "no extra words, no small text, no sentences, no paragraphs, "
        "no watermark, no logo."
    )

    return " ".join(parts).strip()

# ── Main ──────────────────────────────────────────────────────────────────────

def summarize_tl(gemini_key,
                 output_txt=OUTPUT_TXT,
                 prompts_path=PROMPTS_FILE,
                 outdir=None,
                 dated_filenames=False):
    """
    gemini_key    : One Gemini API key (str), multiple keys (list), or a
                    comma-separated string. Rotated automatically on any key error.
    dated_filenames: If True, appends date slug to output filenames
    """
    if outdir is None:
        outdir = SCRIPT_DIR
    os.makedirs(outdir, exist_ok=True)

    with open(prompts_path, encoding="utf-8-sig") as f:
        prompts = json.load(f)

    today     = datetime.now().strftime("%B %d, %Y")
    date_slug = datetime.now().strftime("%b%d")
    outputs   = []

    for topic_key in ["ai", "cybersecurity", "web3"]:
        print(f"\n  [{topic_key}] Processing...")

        briefing = extract_topic_text(output_txt, topic_key)
        if not briefing:
            print(f"    [warn] No briefing found in output.txt — skipping.")
            continue

        prompt_template = prompts.get(topic_key, {}).get("prompt", "")
        if not prompt_template:
            print(f"    [warn] No prompt configured — skipping.")
            continue

        full_prompt = (prompt_template
                       .replace("{today_date}", today)
                       .replace("{briefing}",   briefing))

        print(f"    Calling Gemini...")
        try:
            raw_output = call_gemini_resilient(full_prompt, gemini_key)
        except Exception as e:
            print(f"    [error] Gemini failed: {e}")
            continue

        parsed = parse_tl_output(raw_output)
        parsed["_raw"]           = raw_output
        parsed["_date"]          = today
        parsed["_topic_key"]     = topic_key
        parsed["_topic_display"] = TOPIC_DISPLAY[topic_key]

        backend = (globals().get("IMAGE_BACKEND") or "huggingface").strip().lower()
        if backend in ("none", "off", "disabled") or _IMAGES_DISABLED_REASON:
            print(f"    Images: disabled (placeholders only).")
        elif backend in ("huggingface", "hf"):
            hf_tokens = _parse_gemini_keys(os.environ.get("HF_API_TOKEN"))
            print(f"    Generating images via Hugging Face ({HF_IMAGE_MODEL}, tokens={len(hf_tokens)}, style='{IMAGE_STYLE_PRESET}')...")
        else:
            print(f"    Generating images via Gemini ({GEMINI_IMAGE_MODEL}, style='{IMAGE_STYLE_PRESET}')...")

        for piece in parsed["pieces"]:
            pk         = _plat_key(piece["platform"])
            aspect     = PLATFORM_ASPECT.get(pk, "1:1")
            img_prompt = _build_image_prompt_for_piece(piece)

            # Single image per piece (including Instagram carousels).
            # Also: do not bake slide/caption text into image prompts; we rely on the
            # global style suffix to strongly discourage any text rendering.
            if img_prompt:
                print(f"      [{piece['number']} {piece['platform']}] ({aspect})...")
                img_bytes = generate_image(img_prompt, gemini_key, aspect)
                piece["_img_b64"] = (base64.b64encode(img_bytes).decode()
                                     if img_bytes else None)
                time.sleep(2)
            else:
                piece["_img_b64"] = None

        filename = (f"tl_output_{topic_key}_{date_slug}.json"
                    if dated_filenames else f"tl_output_{topic_key}.json")
        out_path = os.path.join(outdir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        print(f"    Saved -> {filename}")
        outputs.append(out_path)

    return outputs


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Exoasia MRSI Thought Leadership summarizer")
    ap.add_argument("gemini_key",   nargs="?",
                    default=os.environ.get("GEMINI_API_KEY"),
                    help="Gemini API key (or set GEMINI_API_KEY in .env)")
    ap.add_argument("--outdir",     default=SCRIPT_DIR)
    ap.add_argument("--output-txt", default=OUTPUT_TXT)
    ap.add_argument("--style",      default=None,
                    help="Image style preset: bold, cinematic, minimal, neon, corporate. "
                         "Overrides IMAGE_STYLE_PRESET env var and the file-level default.")
    ap.add_argument("--image-model", default=None,
                    help="Override Gemini image model used for image generation. "
                         "Defaults to GEMINI_IMAGE_MODEL env var or a built-in default.")
    ap.add_argument("--image-backend", default=None,
                    help="Image backend: huggingface, gemini, none. "
                         "Defaults to IMAGE_BACKEND env var (default: huggingface).")
    ap.add_argument("--hf-token", default=None,
                    help="Hugging Face token(s) for image generation (comma-separated). "
                         "Or set HF_API_TOKEN in .env (supports multiple lines for rotation).")
    ap.add_argument("--hf-image-model", default=None,
                    help="Hugging Face model id for text-to-image. Defaults to HF_IMAGE_MODEL env var.")
    ap.add_argument("--no-images", action="store_true",
                    help="Skip image generation (always use placeholders).")
    ap.add_argument("--dated-filenames", action="store_true",
                    help="Keep date in JSON output filenames (legacy behavior).")
    args = ap.parse_args()

    # Allow --style CLI arg to override the module-level constant at runtime
    if args.style:
        IMAGE_STYLE_PRESET = args.style.lower()
    if args.image_model:
        GEMINI_IMAGE_MODEL = args.image_model
    if args.image_backend:
        IMAGE_BACKEND = args.image_backend.strip().lower()
    if args.hf_token:
        os.environ["HF_API_TOKEN"] = args.hf_token
    if args.hf_image_model:
        HF_IMAGE_MODEL = args.hf_image_model
    if args.no_images or os.environ.get("TL_NO_IMAGES") in ("1", "true", "TRUE", "yes", "YES"):
        _IMAGES_DISABLED_REASON = "Images disabled (placeholders only)."
        IMAGE_BACKEND = "none"

    gemini_keys = _parse_gemini_keys(args.gemini_key)
    if not gemini_keys:
        print("ERROR: Gemini API key required.")
        print("       Add GEMINI_API_KEY=your_key to your .env file, or pass it as an argument.")
        sys.exit(1)
    print(f"Note: {len(gemini_keys)} Gemini key(s) loaded. Keys rotate automatically on error.")
    print(f"Note: Image style preset: '{IMAGE_STYLE_PRESET}'")
    print(f"Note: Image backend: '{IMAGE_BACKEND}'")
    if IMAGE_BACKEND in ("huggingface", "hf"):
        hf_tokens = _parse_gemini_keys(os.environ.get('HF_API_TOKEN'))
        print(f"Note: HF tokens loaded: {len(hf_tokens)}")
        print(f"Note: HF image model: '{HF_IMAGE_MODEL}'")
    elif IMAGE_BACKEND not in ("none", "off", "disabled"):
        print(f"Note: Gemini image model: '{GEMINI_IMAGE_MODEL}'")

    results = summarize_tl(
        gemini_key      = gemini_keys,
        output_txt      = args.output_txt,
        outdir          = args.outdir,
        dated_filenames = args.dated_filenames,
    )
    print(f"\nDone. {len(results)} JSON file(s) written.")
