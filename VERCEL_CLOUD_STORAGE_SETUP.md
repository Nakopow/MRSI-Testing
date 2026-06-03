# Vercel Cloud Storage Setup Guide

## Problem: Why Updates Don't Persist on Vercel

Vercel's serverless functions have an **ephemeral filesystem**. This means:
- Files created during execution (like `output.txt`, `.docx` files) are **deleted after each function completes**
- Each request starts with a fresh copy of your deployed code
- Any pipeline artifacts generated locally will NOT appear on Vercel

## Solution: Cloud Storage Integration

The codebase already includes a storage abstraction layer (`src/storage.py`) that supports:
- **Supabase Storage** (recommended for Vercel)
- **AWS S3**
- **Local filesystem** (development only)

### Quick Setup with Supabase (Recommended)

#### Step 1: Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and sign up/login
2. Create a new project (choose a region close to your users)
3. Wait for the project to provision (~2 minutes)

#### Step 2: Create Storage Bucket

1. In your Supabase project, go to **Storage** (left sidebar)
2. Click **New bucket**
3. Name it: `mrsi-artifacts`
4. Set **Public** (or Private with CORS configured)
5. Click **Create bucket**

#### Step 3: Get API Keys

1. Go to **Settings** → **API**
2. Copy these values:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **service_role key** (secret): `eyJhbGc...` (starts with eyJ)

⚠️ **Important**: Use the `service_role` key, NOT the `anon` key. The service_role key has full access to storage.

#### Step 4: Configure Vercel Environment Variables

1. Go to your Vercel project dashboard
2. Navigate to **Settings** → **Environment Variables**
3. Add these variables:

```
# Required - Supabase Storage
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key_here
SUPABASE_BUCKET=mrsi-artifacts

# Required - AI
GEMINI_API_KEY=your_gemini_api_key

# Optional
SECRET_KEY=your-secret-key-here
FLASK_DEBUG=false
```

4. Click **Save** for each variable
5. **Redeploy** your project (push to GitHub or click "Redeploy" in Vercel)

#### Step 5: Verify Setup

After deployment, visit `/api/env-check` on your Vercel URL. You should see:

```json
{
  "gemini_configured": true,
  "storage_backend": "supabase",
  "debug_mode": false,
  "vercel_env": true
}
```

### Alternative: AWS S3 Setup

#### Step 1: Create S3 Bucket

1. Go to AWS S3 console
2. Create bucket: `mrsi-artifacts`
3. Configure CORS (Bucket → Permissions → CORS):

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "DELETE"],
    "AllowedOrigins": ["*"],
    "ExposeHeaders": []
  }
]
```

#### Step 2: Create IAM User

1. Go to IAM → Users → Create user
2. Attach policy with S3 access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::mrsi-artifacts",
        "arn:aws:s3:::mrsi-artifacts/*"
      ]
    }
  ]
}
```

3. Create access keys and copy them

#### Step 3: Configure Vercel Environment Variables

```
# Required - AWS S3
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_BUCKET=mrsi-artifacts
AWS_REGION=us-east-1

# Required - AI
GEMINI_API_KEY=your_gemini_api_key
```

## How the Storage Integration Works

### Dashboard Route (`routes/dashboard.py`)

The dashboard now:
1. **First** tries to load digest from cloud storage
2. **Falls back** to local filesystem if cloud fails
3. **Falls back** to sample data if neither exists

### Pipeline Route (`routes/pipeline.py`)

The pipeline now:
1. **Saves** generated artifacts to both local AND cloud storage
2. **Checks** both local and cloud storage for prerequisites
3. **Uses** cloud storage for cross-request persistence

### Storage API (`src/storage.py`)

The `ArtifactStorage` class provides:
- `save_digest(content)` - Save daily digest
- `load_digest()` - Load daily digest
- `save_tlp_json(topic, data)` - Save TLP JSON
- `load_tlp_json(topic)` - Load TLP JSON
- `save_insight(topic, content)` - Save DOCX file
- `save_tlp(topic, content)` - Save TLP DOCX

## Important Limitations

### Vercel Serverless Timeout

- **Hobby plan**: 10 seconds max
- **Pro plan**: 60 seconds max

The scraping and AI pipeline may exceed these limits. Consider:

1. **Hybrid Architecture**: Run pipeline on Railway/Render, serve dashboard on Vercel
2. **Async Processing**: Use Vercel Queues (Pro plan) or external task queue
3. **Upgrade to Pro**: For 60s timeout

### File Size Limits

- Vercel functions: 50MB unzipped bundle size
- Supabase free tier: 1GB storage, 2GB/month bandwidth

## Testing Locally

To test cloud storage locally:

1. Create a `.env` file with your Supabase credentials:

```
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key
SUPABASE_BUCKET=mrsi-artifacts
GEMINI_API_KEY=your_gemini_key
```

2. Run your app:

```bash
python app.py
```

3. The app will automatically use cloud storage when available

## Troubleshooting

### "Missing environment variables"

- Check Vercel dashboard → Settings → Environment Variables
- Ensure variables are set for the correct environment (Production/Preview/Development)
- Redeploy after adding variables

### "Storage operation failed"

- Verify Supabase bucket exists and is accessible
- Check bucket permissions (should be Public or have correct CORS)
- Test connection locally first

### "Function timeout"

- Upgrade to Vercel Pro for 60s timeout
- Or use hybrid architecture with external worker

### "Files not persisting"

- Confirm `STORAGE_BACKEND` is set to `supabase` or `s3`
- Check that cloud storage credentials are correct
- Verify bucket name matches `SUPABASE_BUCKET` or `AWS_BUCKET`

## Full Environment Variables Reference

```bash
# Storage Backend Selection
STORAGE_BACKEND=supabase  # or "s3" or "auto"

# Supabase (if STORAGE_BACKEND=supabase)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbG...  # service_role key
SUPABASE_BUCKET=mrsi-artifacts

# AWS S3 (if STORAGE_BACKEND=s3)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_BUCKET=mrsi-artifacts
AWS_REGION=us-east-1

# AI Services
GEMINI_API_KEY=...

# Flask
SECRET_KEY=your-secret-key
FLASK_DEBUG=false

# Optional
IMAGE_BACKEND=huggingface
HF_API_TOKEN=...
```

## Next Steps

1. Set up Supabase storage following this guide
2. Add environment variables to Vercel
3. Redeploy your application
4. Test by running the pipeline from the dashboard
5. Verify artifacts persist across requests

For production reliability, consider the hybrid architecture described in `VERCEL_DEPLOYMENT.md` where the pipeline runs on a separate worker service (Railway/Render) and uploads results to cloud storage.