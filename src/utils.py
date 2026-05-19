"""
Utility functions shared across the project.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from src.config import FEEDS_PATH, TOPICS


def load_json(file_path: Path) -> Dict[str, Any]:
    """
    Load and parse a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Parsed JSON content as a dictionary
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_feeds() -> Dict[str, List[str]]:
    """
    Load RSS feed URLs from feeds.json.
    
    Returns:
        Dictionary mapping topics to lists of feed URLs
    """
    return load_json(FEEDS_PATH)


def group_articles_by_topic(articles: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group articles by their topic.
    
    Args:
        articles: List of article dictionaries with a 'topic' key
        
    Returns:
        Dictionary mapping topics to lists of articles
    """
    articles_by_topic: Dict[str, List[Dict]] = {topic: [] for topic in TOPICS}
    
    for article in articles:
        topic = article.get("topic")
        if topic and topic in articles_by_topic:
            articles_by_topic[topic].append(article)
    
    return articles_by_topic


def ensure_directory(path: Path) -> None:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Path to the directory
    """
    path.mkdir(parents=True, exist_ok=True)
