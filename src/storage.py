"""
Storage Abstraction Layer for Vercel Deployment

This module provides a unified interface for storing pipeline artifacts
across different storage backends (local filesystem, cloud storage).

For Vercel deployment, use cloud storage backends like:
- AWS S3
- Google Cloud Storage
- Supabase Storage
- Firebase Storage
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def save(self, key: str, content: str, content_type: str = "text/plain") -> bool:
        """Save content to storage."""
        pass
    
    @abstractmethod
    def load(self, key: str) -> Optional[str]:
        """Load content from storage."""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        pass
    
    @abstractmethod
    def list_files(self, prefix: str = "") -> List[str]:
        """List files with a given prefix."""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a file from storage."""
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend (for development)."""
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_path(self, key: str) -> Path:
        """Get full path for a key."""
        return self.base_path / key
    
    def save(self, key: str, content: str, content_type: str = "text/plain") -> bool:
        try:
            path = self._get_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = "w" if "text" in content_type else "wb"
            with open(path, mode, encoding="utf-8" if "text" in content_type else None) as f:
                f.write(content)
            return True
        except Exception as e:
            logger.error(f"Error saving to local storage: {e}")
            return False
    
    def load(self, key: str) -> Optional[str]:
        try:
            path = self._get_path(key)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            return None
        except Exception as e:
            logger.error(f"Error loading from local storage: {e}")
            return None
    
    def exists(self, key: str) -> bool:
        return self._get_path(key).exists()
    
    def list_files(self, prefix: str = "") -> List[str]:
        base = self.base_path / prefix
        if not base.exists():
            return []
        return [str(p.relative_to(self.base_path)) for p in base.rglob("*") if p.is_file()]
    
    def delete(self, key: str) -> bool:
        try:
            path = self._get_path(key)
            if path.exists():
                path.unlink()
            return True
        except Exception as e:
            logger.error(f"Error deleting from local storage: {e}")
            return False


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend for production."""
    
    def __init__(self, bucket_name: str, region: str = "us-east-1"):
        self.bucket_name = bucket_name
        self.region = region
        
        try:
            import boto3
            self.s3 = boto3.client(
                "s3",
                region_name=region,
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
        except ImportError:
            raise ImportError("boto3 is required for S3 storage. Install with: pip install boto3")
    
    def save(self, key: str, content: str, content_type: str = "text/plain") -> bool:
        try:
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=content.encode("utf-8") if isinstance(content, str) else content,
                ContentType=content_type,
            )
            return True
        except Exception as e:
            logger.error(f"Error saving to S3: {e}")
            return False
    
    def load(self, key: str) -> Optional[str]:
        try:
            response = self.s3.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read().decode("utf-8")
        except Exception as e:
            logger.error(f"Error loading from S3: {e}")
            return None
    
    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except:
            return False
    
    def list_files(self, prefix: str = "") -> List[str]:
        try:
            response = self.s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)
            return [obj["Key"] for obj in response.get("Contents", [])]
        except Exception as e:
            logger.error(f"Error listing S3 files: {e}")
            return []
    
    def delete(self, key: str) -> bool:
        try:
            self.s3.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            logger.error(f"Error deleting from S3: {e}")
            return False


class SupabaseStorageBackend(StorageBackend):
    """Supabase Storage backend for production (recommended for Vercel)."""
    
    def __init__(self, bucket_name: str = "mrsi-artifacts"):
        self.bucket_name = bucket_name
        
        try:
            from supabase import create_client
            self.supabase = create_client(
                os.getenv("SUPABASE_URL"),
                os.getenv("SUPABASE_KEY"),
            )
        except ImportError:
            raise ImportError("supabase is required. Install with: pip install supabase")
    
    def save(self, key: str, content: str, content_type: str = "text/plain") -> bool:
        try:
            data = content.encode("utf-8") if isinstance(content, str) else content
            self.supabase.storage.from_(self.bucket_name).upload(
                key, data, {"content-type": content_type}
            )
            return True
        except Exception as e:
            logger.error(f"Error saving to Supabase: {e}")
            return False
    
    def load(self, key: str) -> Optional[str]:
        try:
            data = self.supabase.storage.from_(self.bucket_name).download(key)
            return data.decode("utf-8") if isinstance(data, bytes) else data
        except Exception as e:
            logger.error(f"Error loading from Supabase: {e}")
            return None
    
    def exists(self, key: str) -> bool:
        try:
            self.supabase.storage.from_(self.bucket_name).info(key)
            return True
        except:
            return False
    
    def list_files(self, prefix: str = "") -> List[str]:
        try:
            files = self.supabase.storage.from_(self.bucket_name).list(prefix)
            return [f["name"] for f in files]
        except Exception as e:
            logger.error(f"Error listing Supabase files: {e}")
            return []
    
    def delete(self, key: str) -> bool:
        try:
            self.supabase.storage.from_(self.bucket_name).remove([key])
            return True
        except Exception as e:
            logger.error(f"Error deleting from Supabase: {e}")
            return False


# ── Storage Factory ──────────────────────────────────────────────────────────

def get_storage_backend() -> StorageBackend:
    """
    Factory function to get the appropriate storage backend based on environment.
    
    Priority:
    1. SUPABASE_URL + SUPABASE_KEY → SupabaseStorageBackend
    2. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY → S3StorageBackend
    3. Default → LocalStorageBackend
    """
    storage_type = os.getenv("STORAGE_BACKEND", "auto")
    
    if storage_type == "supabase" or (
        storage_type == "auto" and os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")
    ):
        return SupabaseStorageBackend(
            bucket_name=os.getenv("SUPABASE_BUCKET", "mrsi-artifacts")
        )
    
    elif storage_type == "s3" or (
        storage_type == "auto" and os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    ):
        return S3StorageBackend(
            bucket_name=os.getenv("AWS_BUCKET", "mrsi-artifacts"),
            region=os.getenv("AWS_REGION", "us-east-1"),
        )
    
    else:
        # Default to local storage for development
        return LocalStorageBackend(
            base_path=os.getenv("LOCAL_STORAGE_PATH", ".")
        )


# ── High-level Storage API ───────────────────────────────────────────────────

class ArtifactStorage:
    """High-level storage API for MRSI pipeline artifacts."""
    
    def __init__(self):
        self.backend = get_storage_backend()
    
    def save_article(self, topic: str, content: str) -> bool:
        """Save scraped articles for a topic."""
        return self.backend.save(f"articles/{topic}_articles.txt", content)
    
    def load_article(self, topic: str) -> Optional[str]:
        """Load scraped articles for a topic."""
        return self.backend.load(f"articles/{topic}_articles.txt")
    
    def save_digest(self, content: str) -> bool:
        """Save the daily digest."""
        return self.backend.save("output.txt", content)
    
    def load_digest(self) -> Optional[str]:
        """Load the daily digest."""
        return self.backend.load("output.txt")
    
    def save_insight(self, topic: str, content: bytes) -> bool:
        """Save a Daily Insight DOCX file."""
        return self.backend.save(
            f"insights/Exoasia_MRSI_DailyInsight_{topic}.docx",
            content,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    def save_tlp(self, topic: str, content: bytes) -> bool:
        """Save a Thought Leadership DOCX file."""
        return self.backend.save(
            f"tlps/Exoasia_MRSI_ThoughtLeadership_{topic}.docx",
            content,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    
    def save_tlp_json(self, topic: str, data: dict) -> bool:
        """Save a TLP JSON payload."""
        return self.backend.save(f"tlps/tl_output_{topic}.json", json.dumps(data, indent=2))
    
    def load_tlp_json(self, topic: str) -> Optional[dict]:
        """Load a TLP JSON payload."""
        content = self.backend.load(f"tlps/tl_output_{topic}.json")
        return json.loads(content) if content else None
    
    def get_artifact_status(self) -> dict:
        """Get status of all artifacts."""
        return {
            "articles_scraped": all(
                self.backend.exists(f"articles/{t}_articles.txt")
                for t in ["ai", "cybersecurity", "web3"]
            ),
            "digest_generated": self.backend.exists("output.txt"),
            "insights_count": len(self.backend.list_files("insights/")),
            "tlp_count": len(self.backend.list_files("tlps/")),
        }


# Global storage instance
storage = ArtifactStorage()