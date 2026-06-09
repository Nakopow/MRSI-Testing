"""
Web scraper main entry point - Article file generation.

This module provides the scraping-only workflow, which collects articles
from RSS feeds, enriches them with full text, and saves them to separate
topic files without generating AI summaries.

Usage:
    python scraper_main.py

Output Files:
    - ai_articles.txt
    - cybersecurity_articles.txt  
    - web3_articles.txt

Example:
    >>> from scraper_main import main
    >>> main()  # Run the scraping pipeline
"""

import json
import sys
from scraper import fetch_rss_items, enrich_articles
import textwrap


def main():
    """
    Main orchestration function for the scraping pipeline.
    
    This function performs the following steps:
        1. Load RSS feed URLs from feeds.json
        2. Fetch and filter articles from all feeds
        3. Enrich articles with full text from original URLs
        4. Group articles by topic (ai, cybersecurity, web3)
        5. Save articles to topic-specific text files
    
    Returns:
        None: Results are saved to text files
    
    Raises:
        FileNotFoundError: If feeds.json is missing
        json.JSONDecodeError: If feeds.json contains invalid JSON
        SystemExit: If configuration file is missing or invalid
    
    Example:
        >>> main()
        Loading feeds from feeds.json...
        Fetching RSS feeds...
        Found 50 items from RSS
        Enriching articles with full text...
        Saving articles to topic files...
        Articles saved to ai_articles.txt, cybersecurity_articles.txt, web3_articles.txt
    """
    print("Loading feeds from feeds.json...")
    try:
        with open("feeds.json", "r", encoding="utf-8") as f:
            feeds = json.load(f)
    except FileNotFoundError:
        print("Error: feeds.json not found. Please create it from the feeds.json template.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in feeds.json: {e}")
        sys.exit(1)
            
    print("Fetching RSS feeds...")
    raw_items = fetch_rss_items(feeds)
    print(f"Found {len(raw_items)} items from RSS")

    url_cache: dict[str, dict[str, str]] = {}

    print("Enriching articles with full text...")
    enriched = enrich_articles(raw_items, url_cache)

    print("Grouping articles by topic")
    articles_by_topic: dict[str, list[dict]] = {}
    for article in enriched:
        topic = article["topic"]
        if topic not in articles_by_topic:
            articles_by_topic[topic] = []
        articles_by_topic[topic].append(article)

    # Write articles to topic files using context managers
    print("Saving articles to topic files...")

    saved = []
    for topic, articles in articles_by_topic.items():
        with open(f"{topic}_articles.txt", "w", encoding="utf-8") as f:
            f.write(f"=== {topic.upper()} ===\n\n")

            for article in articles:
                f.write(f"\"{article['title']}\"\n")
                f.write(f"{article['published']}\n\n")

                wrapped_lines = textwrap.wrap(article['body'], width=100)
                f.write("\n")
                for line in wrapped_lines:
                    f.write(line + "\n")

                f.write(f"{article['link']}\n")
                f.write("\n" + "=" * 80 + "\n\n")
        saved.append(f"{topic}_articles.txt")

    print(f"Articles saved to {', '.join(saved)}")


if __name__ == "__main__":
    main()
