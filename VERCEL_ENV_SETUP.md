# Vercel Environment Variables Setup Guide

This guide explains how to configure environment variables for deploying the MRSI Platform to Vercel.

## ⚠️ Important: Why Updates Don't Persist on Vercel

Vercel's serverless functions have an **ephemeral filesystem**. Files created during execution (like `output.txt`, `.docx` files) are **deleted after each function completes**. This is why updates work locally but not on Vercel.

**Solution**: Use cloud storage (Supabase or S3) for persistent file storage. See [VERCEL_CLOUD_STORAGE_SETUP.md](VERCEL_CLOUD_STORAGE_SETUP.md) for detailed setup instructions.

## Required Environment Variables

Add these in **Vercel Dashboard → Project Settings → Environment Variables**:

### Core Variables (Required)

| Variable | Description | Example Value |
|----------|-------------|---------------|
| `GEMINI_API_KEY` | Google Gemini API key for AI summarization | `AIzaSy...` |
| `GEMINI_MODEL` | Gemini model to use | `gemini-2.5-flash` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret key | `dev-secret-key` |
| `FLASK_DEBUG` | Enable debug mode | `false` |
| `STORAGE_BACKEND` | Storage type: `local`, `supabase`, `s3` | `auto` |

### Storage Variables (Required for Persistent Storage)

⚠️ **Without cloud storage, all generated files will be lost after each function invocation.**

#### Supabase Storage (Recommended)
See [VERCEL_CLOUD_STORAGE_SETUP.md](VERCEL_CLOUD_STORAGE_SETUP.md) for step-by-step Supabase setup.

| Variable | Description |
|----------|-------------|
| `STORAGE_BACKEND` | Set to `supabase` |
| `SUPABASE_URL` | Your Supabase project URL (e.g., `https://xxxxx.supabase.co`) |
| `SUPABASE_KEY` | Service role key (NOT anon key) |
| `SUPABASE_BUCKET` | Bucket name (default: `mrsi-artifacts`) |

#### AWS S3 Storage
| Variable | Description |
|----------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_BUCKET` | S3 bucket name |
| `AWS_REGION` | AWS region (default: `us-east-1`) |

### Image Generation Variables (Optional)

| Variable | Description | Default |
|----------|-------------|---------|
| `IMAGE_BACKEND` | Image generation backend: `huggingface`, `gemini`, `none` | `huggingface` |
| `HF_TOKEN` | Hugging Face API token | - |

## Step-by-Step Setup

### 1. Get Your Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Click "Create API Key"
3. Copy the key

### 2. Configure Vercel Environment Variables

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your MRSI project
3. Go to **Settings** → **Environment Variables**
4. Click "Add New" for each variable:

```
Name: GEMINI_API_KEY
Value: AIzaSy... (your key from step 1)
Environment: Production, Preview, Development (select all)
```

### 3. Redeploy

After adding environment variables, trigger a new deployment:
- Go to **Deployments** → Click "Redeploy" on the latest deployment
- Or push a new commit to trigger automatic deployment

## Important Notes

### ⚠️ Function Timeout Limitations

Vercel has strict timeout limits:
- **Hobby Plan**: 10 seconds
- **Pro Plan**: 60 seconds

The MRSI pipeline typically takes **2-5 minutes** to complete. This means:

1. **Pipeline buttons may appear to work** but will timeout before completion
2. **Files generated during execution will be lost** (ephemeral filesystem)
3. **Status polling won't work reliably** (functions are stateless)

### Workarounds

1. **For Testing**: Use local deployment (`python app.py`) for full pipeline testing
2. **For Production**: Consider hybrid architecture (Vercel frontend + external workers)
3. **For Simple Deployment**: Use Railway or Render instead (no timeout limits)

### Local Storage on Vercel

When `STORAGE_BACKEND` is not set or set to `local`:
- Files are saved to the ephemeral filesystem
- Files are **lost after the function completes**
- **This is why updates work locally but not on Vercel**
- Only useful for testing, not production

### Cloud Storage on Vercel (Required for Production)

For persistent storage on Vercel:
1. Set up Supabase Storage (free tier available) - see [VERCEL_CLOUD_STORAGE_SETUP.md](VERCEL_CLOUD_STORAGE_SETUP.md)
2. Add `STORAGE_BACKEND=supabase`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_BUCKET` to Vercel env vars
3. Redeploy your application

The codebase has been updated to automatically use cloud storage when configured, falling back to local storage only for development.

## Troubleshooting

### "GEMINI_API_KEY not found" Error

1. Verify the variable is spelled exactly as `GEMINI_API_KEY`
2. Check it's set for the correct environment (Production/Preview/Development)
3. Redeploy after adding the variable

### Pipeline Timeout

If you see "Function invocation failed" or timeout errors:
- This is expected due to Vercel's timeout limits
- Use local deployment for full pipeline testing
- Consider alternative deployment (Railway/Render)

### Files Not Persisting

- Vercel's filesystem is ephemeral
- Use cloud storage (Supabase/S3) for persistent files
- Or use a hybrid architecture with external workers

## Quick Test

After configuring environment variables, test your deployment:

1. Visit your Vercel URL
2. Click the "Pipeline" dropdown
3. Try "Scrape Articles" (this is the quickest step)
4. Check Vercel Functions logs for any errors

If you see "GEMINI_API_KEY not configured" in logs, the environment variable isn't set correctly.