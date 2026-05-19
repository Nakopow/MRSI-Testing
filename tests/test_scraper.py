"""
Tests for the scraper module.

Note: These tests mock external dependencies (HTTP requests, RSS feeds)
to ensure tests run fast and don't require network access.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# Import scraper components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import fetch_rss_items, extract_article_body
from src.config import TOPIC_KEYWORDS


class TestTopicKeywords:
    """Test topic keyword configuration."""

    def test_all_topics_have_keywords(self):
        """Verify each topic has keywords defined."""
        assert "ai" in TOPIC_KEYWORDS
        assert "cybersecurity" in TOPIC_KEYWORDS
        assert "web3" in TOPIC_KEYWORDS

    def test_keywords_are_strings(self):
        """Verify all keywords are strings."""
        for topic, keywords in TOPIC_KEYWORDS.items():
            assert all(isinstance(kw, str) for kw in keywords)


class TestExtractArticleBody:
    """Test article body extraction."""

    @patch('scraper.requests.get')
    def test_extract_success(self, mock_get):
        """Test successful article extraction."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><article>Test content</article></body></html>"
        mock_response.headers = {"Last-Modified": "Wed, 01 Jan 2025 12:00:00 GMT"}
        mock_get.return_value = mock_response

        body, status, last_modified = extract_article_body("http://example.com")
        
        assert status == "ok"
        assert "Test content" in body

    @patch('scraper.requests.get')
    def test_extract_not_modified(self, mock_get):
        """Test 304 Not Modified response."""
        mock_response = Mock()
        mock_response.status_code = 304
        mock_get.return_value = mock_response

        body, status, last_modified = extract_article_body("http://example.com")
        
        assert status == "not-modified"

    @patch('scraper.requests.get')
    def test_extract_http_error(self, mock_get):
        """Test handling of HTTP errors."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response

        body, status, last_modified = extract_article_body("http://example.com")
        
        assert status == "error"


class TestFetchRssItems:
    """Test RSS feed fetching."""

    @patch('scraper.requests.get')
    @patch('scraper.feedparser.parse')
    def test_fetch_with_keywords(self, mock_parse, mock_get):
        """Test RSS fetching with keyword filtering."""
        # Mock RSS feed response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"<rss></rss>"
        mock_get.return_value = mock_response

        # Mock parsed feed with article
        mock_parse.return_value = {
            "entries": [
                {
                    "title": "New AI Model Released",
                    "summary": "A new artificial intelligence model",
                    "published_parsed": (2025, 1, 1, 12, 0, 0, 0, 0, 0),
                    "link": "http://example.com/article",
                }
            ]
        }

        feeds = {"ai": ["http://example.com/feed"]}
        items = fetch_rss_items(feeds)

        # Should find article with AI keywords since title/summary contains "artificial intelligence"
        assert len(items) >= 1, "Should find at least one article with AI keywords"
        assert items[0]["topic"] == "ai"
        assert items[0]["title"] == "New AI Model Released"
