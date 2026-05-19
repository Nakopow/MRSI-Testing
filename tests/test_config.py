"""
Tests for the configuration module.
"""

import pytest
from src.config import (
    TOPICS,
    TOPIC_KEYWORDS,
    ARTICLE_HOURS_LOOKBACK,
    REQUEST_DELAY_SECONDS,
    MIN_KEYWORD_MATCHES,
    MAX_ARTICLE_WORDS,
    GEMINI_MODEL,
)


class TestConfig:
    """Test configuration values are properly defined."""

    def test_topics_are_defined(self):
        """Verify all required topics are defined."""
        assert "ai" in TOPICS
        assert "cybersecurity" in TOPICS
        assert "web3" in TOPICS
        assert len(TOPICS) == 3

    def test_all_topics_have_keywords(self):
        """Verify each topic has keyword filters."""
        for topic in TOPICS:
            assert topic in TOPIC_KEYWORDS
            assert len(TOPIC_KEYWORDS[topic]) > 0

    def test_numeric_settings_are_positive(self):
        """Verify numeric settings have sensible values."""
        assert ARTICLE_HOURS_LOOKBACK > 0
        assert REQUEST_DELAY_SECONDS >= 0
        assert MIN_KEYWORD_MATCHES > 0
        assert MAX_ARTICLE_WORDS > 0

    def test_gemini_model_is_set(self):
        """Verify Gemini model is configured."""
        assert GEMINI_MODEL is not None
        assert len(GEMINI_MODEL) > 0

    def test_topic_display_names_match_topics(self):
        """Verify all topics have display names."""
        from src.config import TOPIC_DISPLAY_NAMES
        for topic in TOPICS:
            assert topic in TOPIC_DISPLAY_NAMES
