"""
API Keys Management Endpoint for Vercel

This endpoint handles saving, loading, and testing API keys.
Keys can be stored in:
1. Local .env file (development)
2. Cloud storage (Supabase/S3) for Vercel deployment
3. Environment variables (runtime)
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv, set_key, unset_key
from src.storage import storage

# Load environment variables
load_dotenv()

DOTENV_PATH = Path(__file__).parent.parent / ".env"


def save_keys_to_env(keys: dict) -> bool:
    """Save API keys to .env file (for local development)."""
    try:
        for key_name, value in keys.items():
            set_key(str(DOTENV_PATH), key_name, value)
        return True
    except Exception as e:
        print(f"Error saving to .env: {e}")
        return False


def save_keys_to_storage(keys: dict) -> bool:
    """Save API keys to cloud storage (for Vercel deployment)."""
    try:
        # Store keys in a secure JSON file in cloud storage
        keys_data = {
            "keys": keys,
            "updated_at": __import__('datetime').datetime.now().isoformat()
        }
        return storage.backend.save(
            ".api_keys.json",
            json.dumps(keys_data, indent=2),
            content_type="application/json"
        )
    except Exception as e:
        print(f"Error saving to storage: {e}")
        return False


def load_keys_from_storage() -> dict:
    """Load API keys from cloud storage."""
    try:
        content = storage.backend.load(".api_keys.json")
        if content:
            data = json.loads(content)
            return data.get("keys", {})
    except Exception as e:
        print(f"Error loading from storage: {e}")
    return {}


def handler(request):
    """Vercel serverless function for API key management."""
    
    # Handle CORS
    if request.method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": "",
        }
    
    if request.method == "GET":
        # Return current key configuration
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
            
            # Get current key status (not the actual keys for security)
            key_status = {}
            for key in ["GEMINI_API_KEY", "OPENAI_API_KEY", "MAILCHIMP_API_KEY"]:
                key_status[key] = bool(os.getenv(key))
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "storage_type": storage_type,
                    "keys": key_status,
                }),
            }
        except Exception as e:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({"error": str(e)}),
            }
    
    elif request.method == "POST":
        # Save new API keys
        try:
            body = json.loads(request.body) if request.body else {}
            keys = body.get("keys", {})
            
            if not keys:
                return {
                    "statusCode": 400,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "No keys provided"}),
                }
            
            # Save to appropriate storage
            success = False
            
            # Try cloud storage first (for Vercel)
            if os.getenv("SUPABASE_URL") or os.getenv("AWS_ACCESS_KEY_ID"):
                success = save_keys_to_storage(keys)
            
            # Always save to .env for local development
            if DOTENV_PATH.exists() or not success:
                success = save_keys_to_env(keys)
            
            if success:
                # Update environment variables for current session
                for key, value in keys.items():
                    os.environ[key] = value
                
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*",
                    },
                    "body": json.dumps({
                        "success": True,
                        "message": "API keys saved successfully"
                    }),
                }
            else:
                return {
                    "statusCode": 500,
                    "headers": {"Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": "Failed to save keys"}),
                }
                
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": "Invalid JSON"}),
            }
        except Exception as e:
            return {
                "statusCode": 500,
                "headers": {"Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }
    
    return {
        "statusCode": 405,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"error": "Method not allowed"}),
    }