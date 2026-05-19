"""
Tests for utility functions.
"""

import pytest
from src.utils import group_articles_by_topic


class TestGroupArticlesByTopic:
    """Test article grouping functionality."""

    def test_empty_list(self):
        """Verify empty input returns empty dict."""
        result = group_articles_by_topic([])
        assert result == {"ai": [], "cybersecurity": [], "web3": []}

    def test_single_article(self):
        """Verify single article is grouped correctly."""
        articles = [
            {"topic": "ai", "title": "Test Article", "link": "http://example.com"}
        ]
        result = group_articles_by_topic(articles)
        assert len(result["ai"]) == 1
        assert result["ai"][0]["title"] == "Test Article"
        assert result["cybersecurity"] == []
        assert result["web3"] == []

    def test_multiple_articles_same_topic(self):
        """Verify multiple articles from same topic."""
        articles = [
            {"topic": "ai", "title": "Article 1"},
            {"topic": "ai", "title": "Article 2"},
        ]
        result = group_articles_by_topic(articles)
        assert len(result["ai"]) == 2
        assert len(result["cybersecurity"]) == 0
        assert len(result["web3"]) == 0

    def test_multiple_topics(self):
        """Verify articles across multiple topics."""
        articles = [
            {"topic": "ai", "title": "AI Article"},
            {"topic": "cybersecurity", "title": "Security Article"},
            {"topic": "web3", "title": "Crypto Article"},
        ]
        result = group_articles_by_topic(articles)
        assert len(result["ai"]) == 1
        assert len(result["cybersecurity"]) == 1
        assert len(result["web3"]) == 1

    def test_unknown_topic_filtered(self):
        """Verify unknown topics are ignored."""
        articles = [
            {"topic": "unknown", "title": "Unknown Article"},
            {"topic": "ai", "title": "AI Article"},
        ]
        result = group_articles_by_topic(articles)
        assert len(result["ai"]) == 1
        # Unknown topic should not crash, just be ignored
