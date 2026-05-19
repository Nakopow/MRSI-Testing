"""
Web Scraper Project

An intelligent news aggregation and summarization system that automatically
scrapes articles from multiple RSS feeds across three key technology domains.
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__license__ = "MIT"

from src.config import (
    TOPICS,
    TOPIC_KEYWORDS,
    ARTICLE_HOURS_LOOKBACK,
    REQUEST_DELAY_SECONDS,
    GEMINI_MODEL,
)
