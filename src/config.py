"""
Centralized configuration for the web scraper project.

This module contains all hardcoded values that were previously scattered
across multiple files, making it easy to tune settings in one place.
"""

from pathlib import Path
from typing import Dict, List

# ==================== PATHS ====================

# Base directory of the project (where this config.py is located)
BASE_DIR = Path(__file__).resolve().parent.parent

# Directory for output files
OUTPUT_DIR = BASE_DIR

# Configuration file paths
FEEDS_PATH = BASE_DIR / "feeds.json"
PROMPTS_PATH = BASE_DIR / "prompts_config.json"

# ==================== TOPICS ====================

# Supported topics - used throughout the project
TOPICS: List[str] = ["ai", "cybersecurity", "web3"]

# Topic display names (for UI/output)
TOPIC_DISPLAY_NAMES: Dict[str, str] = {
    "ai": "Artificial Intelligence",
    "cybersecurity": "Cybersecurity",
    "web3": "Web3 / Blockchain",
}

# ==================== RSS SCRAPING SETTINGS ====================

# How far back to look for articles (in hours)
ARTICLE_HOURS_LOOKBACK: int = 24

# Maximum number of entries to process per feed
MAX_ENTRIES_PER_FEED: int = 20

# Rate limiting - delay between requests (in seconds)
REQUEST_DELAY_SECONDS: float = 0.5

# Request timeout (in seconds)
REQUEST_TIMEOUT_SECONDS: int = 10

# User agent for HTTP requests
USER_AGENT: str = "NewsDigestBot/1.0 (+https://github.com/Kurtcvsu/News-Crawler-and-Scraper)"

# ==================== ARTICLE EXTRACTION ====================

# Maximum words to extract from an article
MAX_ARTICLE_WORDS: int = 1500

# HTML selectors for content extraction (in order of priority)
CONTENT_SELECTORS: List[str] = [
    "article",
    "main",
    "[role='main']",
]

# HTML tags to remove during extraction
REMOVE_TAGS: List[str] = ["script", "style"]

# ==================== TOPIC KEYWORDS ====================

# Keywords used to filter articles by topic
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "ai": [
        "artificial intelligence", "AI", "machine learning", "neural",
        "GPT", "model", "LLM", "deep learning", "transformer",
        "Philippines", "Llama", "Gemini", "Claude", "ChatGPT",
        "fine-tune", "RAG", "NAIS", "DOST AI"
    ],
    "cybersecurity": [
        "cybersecurity", "security", "vulnerability", "breach",
        "malware", "exploit", "ransomware", "hacking", "cyber",
        "threat", "Philippines", "LockBit", "Conti", "Emotet",
        "Qakbot", "BlackCat", "zero-day", "APT", "Cobalt Strike",
        "CIRT", "DICT-CERT", "PNP-ACG"
    ],
    "web3": [
        "Web3", "web3", "blockchain", "cryptocurrency", "bitcoin", "ethereum",
        "NFT", "DeFi", "decentralized finance", "smart contract",
        "dApp", "decentralized application", "DAO",
        "decentralized autonomous organization", "metaverse",
        "tokenization", "digital assets", "crypto wallet",
        "DeFi protocol", "layer 2", "cross-chain", "GameFi",
        "play-to-earn", "P2E", "yield farming", "staking",
        "liquidity mining", "Web3 infrastructure", "decentralized web",
        "IPFS", "consensus mechanism", "proof of stake",
        "proof of work", "Cadena Act", "Cadena Bill", "Cadena Law",
        "House Bill No. 7913, 19th Congress",
        "PHILIPPINE COUNCIL ON ARTIFICIAL INTELLIGENCE",
        "House Bill/Resolution NO. HB07913",
        "crypto", "altcoin", "token", "coin",
        "solana", "cardano", "polkadot", "avalanche", "ripple", "XRP",
        "binance", "coinbase", "kraken", "exchange",
        "bitcoin ETF", "ethereum ETF", "spot ETF",
        "regulation", "SEC", "Congress", "law", "bill",
        "market", "price", "trading", "bull", "bear",
        "whale", "investor", "fund", "assets",
        "mining", "halving", "reward",
        "ordinal", "inscription", "BRC-20",
        "layer 1", "L2", "rollup", "zk", "optimism", "arbitrum"
    ],
}

# Minimum keyword matches required to include an article
MIN_KEYWORD_MATCHES: int = 2

# ==================== OUTPUT FILES ====================

# Output filename patterns
ARTICLE_FILES: Dict[str, str] = {
    "ai": "ai_articles.txt",
    "cybersecurity": "cybersecurity_articles.txt",
    "web3": "web3_articles.txt",
}

SUMMARY_FILES: Dict[str, str] = {
    "ai": "ai_summary.txt",
    "cybersecurity": "cybersecurity_summary.txt",
    "web3": "web3_summary.txt",
}

# Main output file
DIGEST_FILE: str = "output.txt"

# ==================== API SETTINGS ====================

# Gemini model to use
GEMINI_MODEL: str = "gemini-2.5-flash"

# Environment variable names
ENV_API_KEY: str = "GEMINI_API_KEY"

# ==================== LOGGING ====================

# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL: str = "INFO"

# Whether to log to file
LOG_TO_FILE: bool = False
LOG_FILE: str = "scraper.log"
