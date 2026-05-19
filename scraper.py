"""
Core scraping engine for the AI News Aggregator.

This module provides the core functionality for:
    - Fetching and parsing RSS feeds
    - Filtering articles by topic keywords and date
    - Extracting full article text from URLs
    - Managing URL caching for performance
    - Respecting robots.txt rules
    - Implementing retry logic with exponential backoff

Usage:
    >>> from scraper import fetch_rss_items, enrich_articles
    >>> feeds = {"ai": ["https://feeds.feedburner.com/TechCrunch/"]]
    >>> items = fetch_rss_items(feeds)
    >>> enriched = enrich_articles(items, {})

Data Structures:
    Article (TypedDict):
        - topic: Topic category (ai/cybersecurity/web3)
        - title: Article title
        - link: Article URL
        - published: Publication date
        - body: Full article text

Configuration:
    All settings are centralized in src.config module
"""

import requests
import feedparser
import json
from bs4 import BeautifulSoup
from typing import Dict, List, TypedDict, Literal, Tuple, Optional
from datetime import datetime, timedelta
import urllib.robotparser
import urllib.request
from urllib.parse import urlparse
import time
import logging
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import project config
from src.config import (
    TOPIC_KEYWORDS,
    ARTICLE_HOURS_LOOKBACK,
    MAX_ENTRIES_PER_FEED,
    REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    MAX_ARTICLE_WORDS,
    CONTENT_SELECTORS,
    REMOVE_TAGS,
    MIN_KEYWORD_MATCHES,
)

# Import retry mechanism
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class Article(TypedDict):
    topic: str
    title: str
    link: str
    published: str
    body: str


Status = Literal["ok", "not-modified", "error"]


from collections import OrderedDict
_robots_cache: OrderedDict = OrderedDict()
ROBOTS_CACHE_MAX_SIZE = 100


def _evict_robots_cache():
    """Evict oldest entries if cache exceeds max size."""
    while len(_robots_cache) > ROBOTS_CACHE_MAX_SIZE:
        _robots_cache.popitem(last=False)


def can_fetch(url: str) -> bool:
    """
    Check if the URL can be fetched according to robots.txt rules.
    
    Args:
        url: The URL to check
        
    Returns:
        True if fetching is allowed, False otherwise
    """
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    scheme = parsed_url.scheme if parsed_url.scheme else "https"
    
    # Check if we already have this domain's robots.txt cached
    if domain not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp_url = f"{scheme}://{domain}/robots.txt"
        try:
            # Fetch with timeout to avoid hanging on slow servers
            rp.parse(urllib.request.urlopen(rp_url, timeout=5).read().decode().splitlines())
            _robots_cache[domain] = rp
            _evict_robots_cache()
            logger.info(f"Loaded robots.txt for {domain}")
        except Exception as e:
            logger.warning(f"Could not read robots.txt for {domain}: {e}")
            _robots_cache[domain] = None  # Mark as failed to avoid repeated attempts
    
    # If robots.txt fetch failed, default to allowing the request
    if _robots_cache.get(domain) is None:
        return True
    
    # Check if the path is allowed for our user agent
    return _robots_cache[domain].can_fetch(USER_AGENT, url)


def create_session_with_retries(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """
    Create a requests session with retry logic.
    
    Args:
        retries: Number of retry attempts
        backoff_factor: Exponential backoff factor
        
    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# Create a shared session with retry logic
_session = create_session_with_retries()


def _match_keyword(text: str, keyword: str) -> bool:
    """
    Match keyword in text using word boundary matching to avoid false positives.
    
    Args:
        text: The text to search in
        keyword: The keyword to search for
        
    Returns:
        True if keyword is found as a whole word, False otherwise
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    # Escape special regex characters in keyword
    escaped_keyword = re.escape(keyword_lower)
    
    # Match whole words only (word boundaries)
    pattern = r'\b' + escaped_keyword + r'\b'
    return bool(re.search(pattern, text_lower))


def fetch_rss_items(feeds_dict: Dict[str, List[str]]) -> List[Dict]:
    """Fetch RSS feeds and filter articles by topic keywords."""
    items = []
    cutoff = datetime.now() - timedelta(hours=ARTICLE_HOURS_LOOKBACK)
    
    for topic, urls in feeds_dict.items():
        keywords = TOPIC_KEYWORDS.get(topic, [])
        
        for url in urls:
            try:
                logger.info(f"Fetching feed: {url}")
                resp = _session.get(
                    url,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    headers={"User-Agent": USER_AGENT},
                )
                resp.raise_for_status()

                feed = feedparser.parse(resp.content)
                
                for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
                    title = entry.get("title", "").lower()
                    summary = entry.get("summary", "").lower()
                    published_struct = entry.get("published_parsed")
                    
                    if not published_struct:
                        logger.warning(f"Skipping article without date: {entry.get('title', 'Unknown')}")
                        continue

                    # Use improved keyword matching with word boundaries
                    counter = sum(
                        int(_match_keyword(title, keyword) or _match_keyword(summary, keyword))
                        for keyword in keywords
                    )

                    has_keyword = counter >= MIN_KEYWORD_MATCHES

                    date_released = datetime(*published_struct[:6])

                    formatted_date = date_released.strftime('%b %d, %Y')
                    
                    latest_date = date_released >= cutoff

                    if has_keyword and latest_date:
                        items.append({
                            "topic": topic,
                            "title": entry.get("title", ""),
                            "link": entry.get("link", ""),
                            "published": formatted_date,
                            "summary": entry.get("summary", "")
                        })
            
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
            
            time.sleep(REQUEST_DELAY_SECONDS)
    
    return items


def extract_article_body(url: str, cached_last_modified: Optional[str] = None) -> Tuple[str, Status, Optional[str]]:
    """Fetch the full article page and extract the main text."""
    # Check robots.txt before fetching
    if not can_fetch(url):
        logger.warning(f"Blocked by robots.txt: {url}")
        return "", "error", None
    
    try:
        headers = {
            "User-Agent": USER_AGENT
        }

        if cached_last_modified:
            headers["If-Modified-Since"] = cached_last_modified
        
        response = _session.get(url, timeout=REQUEST_TIMEOUT_SECONDS, headers=headers)

        if response.status_code == 304:
            return "", "not-modified", None

        response.raise_for_status()

        new_last_modified = response.headers.get("Last-Modified")
        
        soup = BeautifulSoup(response.text, "lxml")
        
        for tag in soup(REMOVE_TAGS):
            tag.decompose()
        
        content = None
        for selector in CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                break
        
        if not content:
            content = soup.body if soup.body else soup
        
        text = content.get_text(separator=" ", strip=True)
        words = text.split()[:MAX_ARTICLE_WORDS]
        return " ".join(words), "ok", new_last_modified
    
    except Exception as e:
        logger.error(f"Error extracting article from {url}: {e}")
        return "", "error", None


def enrich_articles(items: List[Dict], url_cache: Dict[str, Dict[str, str]], cache_file: Optional[str] = None) -> List[Article]:
    """Take articles from RSS and fetch their full text from the web.
    
    Args:
        items: List of article dictionaries from RSS feed
        url_cache: In-memory cache for URL data
        cache_file: Optional path to persist cache to disk
    """
    enriched: List[Article] = []
    
    for item in items:
        url = item["link"]

        cached_for_url = url_cache.get(url, {})
        cached_last_modified = cached_for_url.get("last_modified")
        cached_body = cached_for_url.get("body", "")

        body, status, new_last_modified = extract_article_body(url, cached_last_modified=cached_last_modified)

        if status == "ok":
            if new_last_modified:
                url_cache[url] = {
                    "last_modified": new_last_modified,
                    "body": body
                }
        else:
            body = cached_body or item.get("summary", "")
        
        enriched.append(Article(
            topic=item["topic"],
            title=item["title"],
            link=item["link"],
            published=item["published"],
            body=body,
        ))
        
        time.sleep(REQUEST_DELAY_SECONDS)
    
    # Save cache to disk if cache_file is specified
    if cache_file:
        save_url_cache(url_cache, cache_file)
    
    return enriched


def load_url_cache(cache_file: str) -> Dict[str, Dict[str, str]]:
    """Load URL cache from a JSON file.
    
    Args:
        cache_file: Path to the cache file
        
    Returns:
        Dictionary mapping URLs to cached data
    """
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_url_cache(url_cache: Dict[str, Dict[str, str]], cache_file: str) -> None:
    """Save URL cache to a JSON file.
    
    Args:
        url_cache: Dictionary mapping URLs to cached data
        cache_file: Path to save the cache file
    """
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(url_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save URL cache to {cache_file}: {e}") 
