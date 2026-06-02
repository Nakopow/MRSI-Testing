"""
Pipeline Status API for Vercel

This endpoint provides pipeline status information.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage import storage


def handler(request):
    """Vercel serverless function for pipeline status."""
    
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
        try:
            status = storage.get_artifact_status()
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                },
                "body": json.dumps({
                    "scraping": {"status": "idle"},
                    "summarizing": {"status": "idle"},
                    "insights": {"status": "idle"},
                    "tlp": {"status": "idle"},
                    "artifacts": status,
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
    
    return {
        "statusCode": 405,
        "headers": {"Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"error": "Method not allowed"}),
    }

# Export as app for Vercel
app = handler
