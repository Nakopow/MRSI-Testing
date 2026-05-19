# Market Research and Strategic Insight

An automated market intelligence pipeline that scrapes RSS feeds, extracts article text, generates Gemini-based topic briefings, builds branded Daily Insight Word documents, and produces a separate Thought Leadership Pipeline (TLP) content pack for AI, Cybersecurity, and Web3.

## What the program does

This repo has three connected workflows:

1. `scraper_main.py`
   Collects recent articles from configured RSS feeds, filters them by topic keywords, extracts article body text, and writes topic article files.

2. `main.py`
   Runs the full daily intelligence workflow:
   - scrape RSS feeds
   - enrich articles with body text
   - generate topic summaries with Gemini
   - assemble `output.txt`
   - export `Daily_Tech_Briefing.docx`
   - build branded Daily Insight `.docx` files in `insights/`
   - run the Thought Leadership Pipeline

3. Thought Leadership Pipeline
   Uses the finished daily digest in `output.txt` to generate multi-platform thought leadership content per topic, plus branded TLP `.docx` files in `TLPs/`.

## End-to-end pipeline

```text
feeds.json
  -> scraper.py
  -> article filtering by topic/date/keywords
  -> article body extraction + robots.txt check + URL cache
  -> ai_articles.txt / cybersecurity_articles.txt / web3_articles.txt
  -> summarizer.py
  -> ai_summary.txt / cybersecurity_summary.txt / web3_summary.txt
  -> output.txt
  -> Daily_Tech_Briefing.docx
  -> formatter.py
  -> insights/*.docx
  -> tl_summarizer.py
  -> tl_output_ai.json / tl_output_cybersecurity.json / tl_output_web3.json
  -> tl_formatter.py
  -> TLPs/*.docx
```

## Project structure

```text
main.py                  Full pipeline orchestrator
scraper_main.py          Scraping-only entry point
scraper.py               RSS fetching, filtering, extraction, caching
summarizer.py            Gemini daily digest generation
formatter.py             Builds Daily Insight .docx files from output.txt
tl_summarizer.py         Builds TLP JSON content packs and generates images
tl_formatter.py          Builds branded TLP .docx files from TLP JSON
src/config.py            Centralized config
src/utils.py             Shared utilities
feeds.json               RSS sources by topic
prompts_config.json      Daily digest prompts
tl_prompts_config.json   Thought Leadership prompts
tests/                   Unit tests
insights/                Generated Daily Insight files
TLPs/                    Generated Thought Leadership files
```

## Topics covered

- `ai`
- `cybersecurity`
- `web3`

These are the canonical topic keys used across scraping, summarization, filenames, and output generation.

## Main features

- Multi-topic RSS aggregation from `feeds.json`
- Keyword-based topic filtering using `src/config.py`
- 24-hour article lookback window
- Full-text article extraction with Beautiful Soup
- `robots.txt` checks before article fetches
- Retry-enabled HTTP session for scraping
- URL cache persisted in `.url_cache.json`
- Gemini daily digest generation with API key rotation support
- Per-topic summary files plus unified `output.txt`
- Word export for daily briefing
- Daily Insight `.docx` generation from the digest
- Thought Leadership Pipeline for multi-platform content packs
- Image generation support for TLP outputs using Hugging Face or Gemini

## Requirements

- Python 3.8+
- A Gemini API key in `GEMINI_API_KEY`
- Internet access when running the scraper and Gemini/TLP steps
- Required Word templates present in the repo root:
  - `Exoasia_MRSI_DailyInsight_Mar9_AI.docx`
  - `Exoasia_MRSI_ThoughtLeadership_Template.docx`

## Installation

```bash
python -m venv .venv
```

Windows:

```bash
.\.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirement.txt
```

Or:

```bash
pip install -e .
```

## Environment variables

Create a `.env` file in the project root.

### Required

```env
GEMINI_API_KEY=your_gemini_key
```

`summarizer.py` and `tl_summarizer.py` both support multiple Gemini keys. You can either:

- provide a comma-separated value:

```env
GEMINI_API_KEY=key1,key2,key3
```

- or repeat the key on multiple lines in `.env`:

```env
GEMINI_API_KEY=key1
GEMINI_API_KEY=key2
GEMINI_API_KEY=key3
```

### Optional TLP image settings

```env
HF_API_TOKEN=your_huggingface_token
IMAGE_BACKEND=huggingface
HF_IMAGE_MODEL=runwayml/stable-diffusion-v1-5
GEMINI_IMAGE_MODEL=imagen-4.0-fast-generate-001
IMAGE_STYLE_PRESET=bold
TL_NO_IMAGES=false
```

Supported `IMAGE_BACKEND` values:

- `huggingface`
- `gemini`
- `none`

Supported `IMAGE_STYLE_PRESET` values in `tl_summarizer.py`:

- `bold`
- `cinematic`
- `minimal`
- `neon`
- `corporate`

## Configuration

Most runtime settings live in [src/config.py](/C:/Users/Owner/Documents/GitHub/Market-Research-and-Strategic-Insight/src/config.py).

### Core scraper settings

| Setting | Default |
|---|---:|
| `ARTICLE_HOURS_LOOKBACK` | `24` |
| `MAX_ENTRIES_PER_FEED` | `20` |
| `REQUEST_DELAY_SECONDS` | `0.5` |
| `REQUEST_TIMEOUT_SECONDS` | `10` |
| `MAX_ARTICLE_WORDS` | `1500` |
| `MIN_KEYWORD_MATCHES` | `2` |
| `GEMINI_MODEL` | `gemini-2.5-flash` |

### Files and prompts

- `feeds.json` contains the RSS sources grouped by topic
- `prompts_config.json` controls the daily digest prompts
- `tl_prompts_config.json` controls the Thought Leadership content prompts

### Output filenames

Configured in `src/config.py`:

- `ai_articles.txt`
- `cybersecurity_articles.txt`
- `web3_articles.txt`
- `ai_summary.txt`
- `cybersecurity_summary.txt`
- `web3_summary.txt`
- `output.txt`

## Usage

### 1. Run scraping only

```bash
python scraper_main.py
```

Generates:

- `ai_articles.txt`
- `cybersecurity_articles.txt`
- `web3_articles.txt`

### 2. Run the full daily pipeline

```bash
python main.py
```

Generates:

- `ai_summary.txt`
- `cybersecurity_summary.txt`
- `web3_summary.txt`
- `output.txt`
- `Daily_Tech_Briefing.docx`
- `insights/Exoasia_MRSI_DailyInsight_<Date>_<Topic>.docx`
- `tl_output_ai.json`
- `tl_output_cybersecurity.json`
- `tl_output_web3.json`
- `TLPs/Exoasia_MRSI_ThoughtLeadership_<Date>_<Topic>.docx`

### 3. Run the Daily Insight formatter directly

```bash
python formatter.py --input output.txt --outdir insights
```

### 4. Run the Thought Leadership summarizer directly

```bash
python tl_summarizer.py
```

Useful flags:

```bash
python tl_summarizer.py --style bold --image-backend huggingface
python tl_summarizer.py --no-images
python tl_summarizer.py --dated-filenames
```

### 5. Run the Thought Leadership formatter directly

```bash
python tl_formatter.py --outdir TLPs
```

## Thought Leadership Pipeline

The TLP starts after `main.py` finishes building `output.txt`.

### TLP step 1: `tl_summarizer.py`

For each topic:

- reads the topic section from `output.txt`
- loads the matching prompt from `tl_prompts_config.json`
- calls Gemini to create a structured content pack
- parses the response into platform-specific pieces
- optionally generates one image per piece
- saves the result to `tl_output_<topic>.json`

Each topic produces five platform content pieces:

- LinkedIn
- YouTube / Video Script
- Instagram Carousel
- Facebook
- TikTok

The generated JSON includes:

- editorial note
- piece number
- platform
- angle
- format
- objective
- image guidance
- copy, script, slides, or caption depending on platform
- posting notes or production notes
- optional base64-encoded image bytes

### TLP step 2: `tl_formatter.py`

This step:

- reads each `tl_output_*.json`
- injects content into the branded TLP Word template
- embeds generated images or placeholders
- writes final `.docx` files into `TLPs/`

## Daily Insight formatter

`formatter.py` reads `output.txt`, splits it into topic sections, parses:

- title
- subtitle
- executive summary bullets
- body sections
- thought leadership questions
- sources

It then writes one branded `.docx` per topic into `insights/`.

## Output reference

### Scraper outputs

- `ai_articles.txt`
- `cybersecurity_articles.txt`
- `web3_articles.txt`

### Daily digest outputs

- `ai_summary.txt`
- `cybersecurity_summary.txt`
- `web3_summary.txt`
- `output.txt`
- `Daily_Tech_Briefing.docx`

### Daily Insight outputs

- `insights/Exoasia_MRSI_DailyInsight_<Date>_AI.docx`
- `insights/Exoasia_MRSI_DailyInsight_<Date>_CyberSec.docx`
- `insights/Exoasia_MRSI_DailyInsight_<Date>_Web3.docx`

### Thought Leadership outputs

- `tl_output_ai.json`
- `tl_output_cybersecurity.json`
- `tl_output_web3.json`
- `TLPs/Exoasia_MRSI_ThoughtLeadership_<Date>_AI.docx`
- `TLPs/Exoasia_MRSI_ThoughtLeadership_<Date>_CyberSec.docx`
- `TLPs/Exoasia_MRSI_ThoughtLeadership_<Date>_Web3.docx`

### Cache output

- `.url_cache.json`

## Key modules

### `scraper.py`

Responsible for:

- `fetch_rss_items()`
- `extract_article_body()`
- `enrich_articles()`
- `can_fetch()`
- `load_url_cache()`
- `save_url_cache()`

### `summarizer.py`

Responsible for:

- Gemini client initialization
- API key loading and key rotation
- per-topic summary generation
- unified digest generation

### `formatter.py`

Responsible for:

- parsing `output.txt`
- splitting digest sections by topic
- producing branded Daily Insight `.docx` files

### `tl_summarizer.py`

Responsible for:

- extracting each topic briefing from `output.txt`
- calling Gemini for structured TLP content
- parsing TLP content into JSON
- generating platform images
- writing `tl_output_*.json`

### `tl_formatter.py`

Responsible for:

- reading TLP JSON
- patching the branded template
- embedding generated images
- writing final TLP `.docx` files

## Testing

Run tests with:

```bash
pytest
```

Current test files:

- `tests/test_config.py`
- `tests/test_scraper.py`
- `tests/test_utils.py`

## Troubleshooting

### `GEMINI_API_KEY` not set

Add it to `.env` or export it before running the pipeline.

### No articles found

Check:

- `feeds.json`
- RSS source availability
- `TOPIC_KEYWORDS`
- `ARTICLE_HOURS_LOOKBACK`
- `MIN_KEYWORD_MATCHES`

### Template not found

The following files must exist in the repo root:

- `Exoasia_MRSI_DailyInsight_Mar9_AI.docx`
- `Exoasia_MRSI_ThoughtLeadership_Template.docx`

### TLP images are missing

Check:

- `IMAGE_BACKEND`
- `HF_API_TOKEN` if using Hugging Face
- Gemini image model availability if using Gemini
- `--no-images` or `TL_NO_IMAGES`

If image generation fails, the TLP formatter can still build the final `.docx` using placeholders.

### Robots.txt blocks an article

That source will be skipped for body extraction. The pipeline falls back to cached content or the RSS summary when available.

## Notes

- `main.py` always runs the Daily Insight formatter and the Thought Leadership Pipeline after the digest is created.
- `scraper_main.py` is the lightweight option if you only want article collection.
- The repo currently includes generated sample outputs in `insights/`, `TLPs/`, and `tl_output_*.json`.
