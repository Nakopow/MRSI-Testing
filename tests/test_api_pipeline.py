"""
Tests for the Vercel API pipeline endpoint.

These tests verify the serverless function for pipeline status.
"""

import pytest
from unittest.mock import patch, Mock
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.pipeline import handler, app


class TestVercelPipelineAPI:
    """Test the Vercel serverless pipeline API."""

    def test_handler_returns_status_on_get(self):
        """Test that GET request returns pipeline status."""
        mock_request = Mock()
        mock_request.method = "GET"
        
        with patch("api.pipeline.storage.get_artifact_status") as mock_status:
            mock_status.return_value = {
                "articles_scraped": True,
                "digest_generated": True,
                "insights_count": 3,
                "tlp_count": 3,
            }
            
            result = handler(mock_request)
            
            assert result["statusCode"] == 200
            body = json.loads(result["body"])
            assert "scraping" in body
            assert "summarizing" in body
            assert "insights" in body
            assert "tlp" in body
            assert "artifacts" in body
            assert "Access-Control-Allow-Origin" in result["headers"]

    def test_handler_handles_cors_options(self):
        """Test that OPTIONS request returns CORS headers."""
        mock_request = Mock()
        mock_request.method = "OPTIONS"
        
        result = handler(mock_request)
        
        assert result["statusCode"] == 200
        assert "Access-Control-Allow-Origin" in result["headers"]
        assert "Access-Control-Allow-Methods" in result["headers"]
        assert "Access-Control-Allow-Headers" in result["headers"]

    def test_handler_returns_405_for_other_methods(self):
        """Test that methods other than GET and OPTIONS return 405."""
        for method in ["POST", "PUT", "DELETE", "PATCH"]:
            mock_request = Mock()
            mock_request.method = method
            
            result = handler(mock_request)
            
            assert result["statusCode"] == 405
            assert "Access-Control-Allow-Origin" in result["headers"]

    def test_handler_handles_errors(self):
        """Test that errors are handled gracefully."""
        mock_request = Mock()
        mock_request.method = "GET"
        
        with patch("api.pipeline.storage.get_artifact_status") as mock_status:
            mock_status.side_effect = Exception("Storage error")
            
            result = handler(mock_request)
            
            assert result["statusCode"] == 500
            body = json.loads(result["body"])
            assert "error" in body

    def test_app_export(self):
        """Test that handler is exported as app for Vercel."""
        assert app is handler