# TLP Platform — by Exoasia

An automated Thought Leadership Pipeline that scrapes RSS feeds, generates Gemini-powered daily briefings, produces branded Daily Insight and TLP documents, and serves everything through a multi-user web dashboard with Google OAuth and per-user preferences.

---

## What it does

Three connected workflows feed into the web dashboard:

| Step | Script | Output |
|------|--------|--------|
| Scrape | `scraper_main.py` | `*_articles.txt` per topic |
| Summarise | `summarizer.py` | `*_summary.txt`, `output.txt`, `Daily_Tech_Briefing.docx` |
| Daily Insights | `formatter.py` | `insights/*.docx` |
| TLP generation | `tl_summarizer.py` + `tl_formatter.py` | `tl_output_*.json`, `TLPs/*.docx` |
| Web dashboard | `app.py` (Flask) | Live UI, per-user settings, scheduling |

Topics covered: **AI**, **Cybersecurity**, **Web3** (custom topics can be added in the dashboard).

---

## Quick start

```bash
# 1. Clone and create a virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and fill in the environment file
cp .env.example .env
# edit .env — at minimum set GEMINI_API_KEY and DASHBOARD_PASSWORD

# 4. Start the web server
python app.py
# → http://localhost:8000
```

---

## Web dashboard

The Flask app (`app.py`) exposes the full platform UI.

### Routes

| Route | Description |
|-------|-------------|
| `/` | Dashboard overview (metrics, recent activity) |
| `/v2/insights` | Daily Insight documents per topic |
| `/v2/tlp` | TLP & Newsletter content packs |
| `/autopost` | Auto-post schedule and platform guidance |
| `/schedule` | Pipeline run schedule (daily / weekly / manual) |
| `/apikeys` | API key management |
| `/settings` | Brand settings |
| `/login` | Sign in (username/password or Google) |
| `/register` | Create account |
| `/logout` | Sign out |

### Pipeline controls

The **Pipeline** button in the top bar lets you run any step individually or the full pipeline end-to-end, with live status polling.

---

## Authentication

### Username / password

Set in `.env`:

```env
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=your_password
```

### Google OAuth (recommended)

1. Go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. Create an **OAuth 2.0 Client ID** (Web application)
3. Add Authorised redirect URIs:
   - `http://localhost:8000/auth/google/callback` (local)
   - `https://your-domain.com/auth/google/callback` (production)
4. Add to `.env`:

```env
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
ALLOWED_GMAIL=you@gmail.com  # comma-separated; blank = any Google account
```

### User accounts

Every user (registered or Google sign-in) gets their own row in the database. Per-user settings stored in the `users` table:

- Pipeline schedule
- Brand settings
- Auto-post preferences
- API keys (Gemini, OpenAI, Mailchimp)

---

## Environment variables

Copy `.env.example` to `.env` and fill in the values below.

### Required

```env
GEMINI_API_KEY=your_gemini_key      # https://aistudio.google.com/apikey
DASHBOARD_PASSWORD=change_me_now
SECRET_KEY=<random 32-byte hex>     # python -c "import secrets; print(secrets.token_hex(32))"
```

### Authentication (optional but recommended)

```env
DASHBOARD_USERNAME=admin            # default: admin
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
ALLOWED_GMAIL=you@gmail.com
```

### Database

```env
# Default: SQLite file (users.db) — no setup needed for local dev
# For production set DATABASE_URL to your Supabase / PostgreSQL connection string:
DATABASE_URL=postgresql://postgres.[ref]:[password]@[host]:6543/postgres
```

### Cloud storage (Supabase)

```env
STORAGE_BACKEND=supabase            # auto | supabase | s3 | local
SUPABASE_URL=https://[ref].supabase.co
SUPABASE_KEY=your_service_role_key
SUPABASE_BUCKET=tlp-artifacts
```

### AI image generation (optional)

```env
IMAGE_BACKEND=huggingface           # huggingface | gemini | none
HF_API_TOKEN=
HF_IMAGE_MODEL=runwayml/stable-diffusion-v1-5
GEMINI_IMAGE_MODEL=imagen-4.0-fast-generate-001
IMAGE_STYLE_PRESET=bold             # bold | cinematic | minimal | neon | corporate
TL_NO_IMAGES=false
```

### Scraper tuning (optional)

```env
ARTICLE_HOURS_LOOKBACK=24
MAX_ENTRIES_PER_FEED=20
REQUEST_DELAY_SECONDS=0.5
REQUEST_TIMEOUT_SECONDS=10
MAX_ARTICLE_WORDS=1500
MIN_KEYWORD_MATCHES=2
GEMINI_MODEL=gemini-2.5-flash
```

---

## Project structure

```
app.py                   Flask app factory — DB init, blueprint registration, scheduler
models.py                SQLAlchemy User model with per-user preferences JSON
routes/
  auth.py                Login, registration, Google OAuth callback
  dashboard.py           Dashboard pages and settings API (per-user)
  pipeline.py            Pipeline step endpoints (scrape, summarise, insights, TLP)
  tlp_insights.py        TLP & Insights page endpoints + generation trigger
  api.py                 Status API
src/
  config.py              Centralised runtime config
  scheduler.py           APScheduler integration (Railway / long-running only)
  storage.py             Storage backend abstraction (local / Supabase / S3)
  utils.py               Shared utilities
static/
  css/main.css           Design system
  js/app.js              Dashboard interactivity, pipeline polling, schedule UI
templates/
  base.html              Sidebar nav, topbar, pipeline menu
  auth/
    login.html           Sign-in page (Google button + password form)
    register.html        Registration page with password strength meter
  dashboard/
    _dashboard_page.html Overview metrics and recent activity
    _insights_page.html  Daily Insight file list
    _tlp_page.html       TLP content cards
    _schedule_page.html  Pipeline schedule picker with custom time inputs
    _apikeys_page.html   API key management
    _settings_page.html  Brand settings
  v2/
    tlp.html             Enhanced TLP view
    insights.html        Enhanced Insights view
main.py                  Full pipeline orchestrator (CLI)
scraper_main.py          Scraping-only entry point
scraper.py               RSS fetch, filter, body extraction, URL cache
summarizer.py            Gemini daily digest generation + key rotation
formatter.py             Daily Insight .docx builder
tl_summarizer.py         TLP content generation (Gemini) + image generation
tl_formatter.py          Branded TLP .docx builder
feeds.json               RSS sources by topic
prompts_config.json      Daily digest prompts
tl_prompts_config.json   TLP prompts
tests/                   Unit tests
insights/                Generated Daily Insight .docx files
TLPs/                    Generated TLP .docx files
```

---

## Pipeline flow

```
feeds.json
  → scraper.py           RSS fetch + keyword filter + body extraction
  → *_articles.txt
  → summarizer.py        Gemini topic summaries + unified digest
  → *_summary.txt / output.txt / Daily_Tech_Briefing.docx
  → formatter.py         Per-topic branded .docx
  → insights/*.docx
  → tl_summarizer.py     Structured TLP JSON via Gemini + optional images
  → tl_output_*.json
  → tl_formatter.py      Branded TLP .docx
  → TLPs/*.docx
```

---

## Running the pipeline from the CLI

```bash
# Scrape only
python scraper_main.py

# Full pipeline (scrape → digest → insights → TLP)
python main.py

# Daily Insight formatter only
python formatter.py --input output.txt --outdir insights

# TLP summariser only
python tl_summarizer.py
python tl_summarizer.py --style bold --image-backend huggingface
python tl_summarizer.py --no-images

# TLP formatter only
python tl_formatter.py --outdir TLPs
```

---

## Deployment

### Local

```bash
python app.py
```

### Vercel (serverless)

- Set all env vars in the Vercel dashboard
- `STORAGE_BACKEND=supabase` — Vercel has no persistent filesystem
- `DATABASE_URL` → Supabase **Transaction pooler** connection string (port 6543)
- `VERCEL=1` is set automatically; the app disables APScheduler and uses `NullPool`

### Railway

- `DATABASE_URL` → Supabase **Direct connection** string (port 5432) or Railway's own PostgreSQL
- APScheduler runs as a background thread; the pipeline schedule set in the dashboard is respected

---

## Database

SQLite (`users.db`) is used by default — no configuration needed for local development.

For production, set `DATABASE_URL` to any PostgreSQL connection string. Supabase is the recommended option:

1. Supabase dashboard → **Settings → Database → Connection string → URI**
2. Copy the **Transaction pooler** URI for Vercel, or **Direct connection** for Railway
3. Set `DATABASE_URL` in your environment

`db.create_all()` runs on app startup — the `users` table is created automatically.

---

## Testing

```bash
pytest
```

Test files: `tests/test_config.py`, `tests/test_scraper.py`, `tests/test_utils.py`

---

## Troubleshooting

**`GEMINI_API_KEY` not set** — Add it to `.env` or export it before running.

**No articles found** — Check `feeds.json`, RSS source availability, `TOPIC_KEYWORDS`, `ARTICLE_HOURS_LOOKBACK`, and `MIN_KEYWORD_MATCHES`.

**Google sign-in fails** — Confirm the redirect URI in Google Cloud Console exactly matches `http(s)://your-domain/auth/google/callback`. On localhost use port 8000.

**Database connection error (Supabase)** — Make sure `DATABASE_URL` uses `postgresql://` (not `postgres://`), and that the password doesn't contain unescaped special characters. SSL is added automatically.

**TLP images missing** — Check `IMAGE_BACKEND`, `HF_API_TOKEN` (Hugging Face), or Gemini image model availability. The TLP formatter falls back to placeholders if image generation fails.

**Template not found** — The following files must exist in the repo root:
- `Exoasia_TLP_DailyInsight_Template.docx`
- `Exoasia_TLP_ThoughtLeadership_Template.docx`
