# Vercel Deployment Guide for MRSI Platform

This guide explains how to deploy the MRSI Platform to Vercel with the necessary architectural changes.

## ⚠️ Important Limitations

Vercel is designed for serverless functions with the following constraints:

| Constraint | Vercel Limit |
|------------|--------------|
| Max function duration | 10-60 seconds (Hobby: 10s, Pro: 60s) |
| Max bundle size | 50MB (unzipped) |
| No persistent filesystem | Ephemeral storage only |
| No long-running processes | Functions are stateless |

**The scraping and AI processing pipeline may exceed these limits.** For production use, consider:
- **Railway.app** - Better for long-running Python processes
- **Render.com** - Supports background workers
- **AWS/GCP** - Full control with EC2/Compute Engine

## Architecture Changes for Vercel

### 1. Storage Abstraction

Since Vercel doesn't have persistent storage, we've created `src/storage.py` which supports:

- **Supabase Storage** (recommended)
- **AWS S3**
- **Local filesystem** (development only)

### 2. Serverless API Structure

The `api/` directory contains Vercel serverless functions:

```
api/
├── index.py          # Main Flask app entry point
├── pipeline.py       # Pipeline status endpoint
└── trigger.py        # Async pipeline trigger (uses queues)
```

## Deployment Steps

### Step 1: Set Up Cloud Storage

#### Option A: Supabase Storage (Recommended)

1. Create a [Supabase](https://supabase.com) project
2. Go to **Storage** → Create a new bucket named `mrsi-artifacts`
3. Set bucket to **Public** or configure CORS
4. Get your credentials from **Settings** → **API**

#### Option B: AWS S3

1. Create an S3 bucket named `mrsi-artifacts`
2. Configure CORS for the bucket
3. Create IAM user with S3 access
4. Get access keys

### Step 2: Configure Environment Variables

In Vercel dashboard, go to **Project Settings** → **Environment Variables** and add:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key

# Storage (Supabase recommended)
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_service_role_key
SUPABASE_BUCKET=mrsi-artifacts

# Or AWS S3
# STORAGE_BACKEND=s3
# AWS_ACCESS_KEY_ID=your_access_key
# AWS_SECRET_ACCESS_KEY=your_secret_key
# AWS_BUCKET=mrsi-artifacts
# AWS_REGION=us-east-1

# Optional
SECRET_KEY=your-secret-key-here
FLASK_DEBUG=false
IMAGE_BACKEND=huggingface
HF_API_TOKEN=your_huggingface_token
```

### Step 3: Deploy to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod
```

Or connect your GitHub repository in the Vercel dashboard for automatic deployments.

### Step 4: Configure Build Settings

In Vercel dashboard → **Project Settings** → **Build & Development Settings**:

- **Framework Preset**: Other
- **Root Directory**: `./`
- **Output Directory**: `static/`
- **Install Command**: `pip install -r requirements.txt`

## Pipeline Execution Model

Due to Vercel's timeout limits, the pipeline uses an **async trigger model**:

1. **Frontend** sends a POST request to `/pipeline/scrape` (or other endpoints)
2. **API** validates the request and returns immediately
3. **Background processing** happens via:
   - **Option A**: Vercel Cron + Queues (Pro plan required)
   - **Option B**: External service like Zapier/Make.com
   - **Option C**: Hybrid approach with separate worker service

### Recommended: Hybrid Architecture

For reliable pipeline execution, use this architecture:

```
┌─────────────────┐     ┌─────────────────┐
│   Vercel        │     │   Worker        │
│   (Frontend +   │────▶│   Service       │
│   API)          │     │   (Railway/     │
│                 │     │    Render)      │
└─────────────────┘     └─────────────────┘
        │                        │
        ▼                        ▼
┌─────────────────────────────────────────┐
│         Cloud Storage (S3/Supabase)     │
└─────────────────────────────────────────┘
```

1. Vercel handles the dashboard and API
2. A separate worker service (Railway/Render) runs the pipeline
3. Both share cloud storage for artifacts

## Creating a Worker Service

Create a separate repository or add to this one:

```python
# worker.py - Run this on Railway/Render
import time
from scraper_main import main as run_scraping
from summarizer import generate_daily_digest
from main import run_formatter, run_tl_pipeline

def run_full_pipeline():
    """Run the complete MRSI pipeline."""
    print("Starting pipeline...")
    
    # Step 1: Scrape
    run_scraping()
    
    # Step 2: Summarize
    # ... (load articles and generate digest)
    
    # Step 3: Generate insights
    run_formatter("output.txt")
    
    # Step 4: Generate TLPs
    run_tl_pipeline("output.txt")
    
    print("Pipeline complete!")

# Run on schedule (e.g., every 6 hours)
if __name__ == "__main__":
    run_full_pipeline()
```

## Vercel Cron Configuration

Add to `vercel.json` for scheduled triggers (Pro plan):

```json
{
  "crons": {
    "trigger-pipeline": {
      "path": "/api/trigger-pipeline",
      "schedule": "0 */6 * * *"
    }
  }
}
```

## Troubleshooting

### Function Timeout

If you see timeout errors:
1. Upgrade to Vercel Pro for 60s timeout
2. Use the hybrid architecture with external workers
3. Optimize code to reduce execution time

### Storage Errors

If storage operations fail:
1. Check environment variables are set correctly
2. Verify bucket permissions/CORS
3. Test storage connection locally first

### Import Errors

If you see import errors:
1. Ensure `requirements.txt` includes all dependencies
2. Check Python version is 3.8+
3. Verify package names are correct

## Cost Considerations

| Service | Free Tier | Paid |
|---------|-----------|------|
| Vercel | 100GB bandwidth, 100k function invocations | $20/month for Pro |
| Supabase | 500MB storage, 50k daily active users | $25/month for Pro |
| AWS S3 | 5GB storage | ~$0.023/GB/month |

## Alternative: Deploy to Railway

For a simpler deployment without these limitations:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Deploy
railway up
```

Railway supports:
- Long-running processes
- Persistent storage
- Background workers
- Scheduled tasks

## Summary

While Vercel deployment is possible, the MRSI Platform's pipeline architecture is better suited for traditional hosting platforms like Railway or Render. The hybrid approach (Vercel frontend + external workers) provides the best of both worlds but adds complexity.

For production reliability, we recommend:
1. **Small scale/testing**: Vercel with local storage
2. **Production**: Railway or Render with persistent storage
3. **Enterprise**: AWS/GCP with full infrastructure control