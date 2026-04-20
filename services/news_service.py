"""
news_service.py — NewsAPI integration with web search fallback.

If NewsAPI returns no articles for a topic, automatically falls back to
DuckDuckGo / Wikipedia web search and returns results in the same format.
"""

import re
import logging
import requests
from typing import List, Dict, Optional, Tuple

import config

log = logging.getLogger(__name__)

VALID_CATEGORIES = frozenset({
    "business", "entertainment", "general",
    "health", "science", "sports", "technology"
})

_STOP_WORDS = frozenset({
    "tell", "me", "the", "news", "about", "latest",
    "headlines", "today", "give", "what", "is", "are",
    "any", "some", "recent", "top", "current"
})


# ─── Text Cleaning ────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"[^\w\s.,!?'-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─── Topic Extraction ─────────────────────────────────────────────────────────

def extract_topic(query: str) -> str:
    query = query.strip()
    if not query or query.lower() == "general":
        return "general"
    if len(query.split()) <= 5:
        return query
    words = re.sub(r"[^\w\s]", "", query.lower()).split()
    topic_words = [w for w in words if w not in _STOP_WORDS]
    topic = " ".join(topic_words).strip()
    return topic if topic else "general"


# ─── Web Search Fallback ──────────────────────────────────────────────────────

def _web_search_fallback(topic: str) -> Tuple[Optional[List[Dict]], str]:
    """
    When NewsAPI has no results, fall back to DuckDuckGo / Wikipedia.
    Returns articles in the same dict format as NewsAPI results.
    """
    try:
        from services.web_search_service import _search_ddgs_new, _search_ddgs_old, _search_wikipedia
        query = f"{topic} news"

        results = _search_ddgs_new(query) or _search_ddgs_old(query) or _search_wikipedia(query)
        if not results:
            return None, f"No news or web results found for '{topic}'."

        articles = []
        for r in results[:5]:
            title = r.get("title", "").strip()
            body  = r.get("body", "").strip()
            href  = r.get("href", "").strip()
            if title:
                articles.append({
                    "title":       title,
                    "description": body[:220] if body else "",
                    "source":      "Web Search",
                    "published":   "",
                    "url":         href,
                })

        if articles:
            log.info("Web search fallback: %d results for '%s'", len(articles), topic)
            return articles, topic

        return None, f"No news or web results found for '{topic}'."

    except Exception as exc:
        log.warning("Web search fallback failed: %s", exc)
        return None, f"No news found for '{topic}'."


# ─── Main Fetch ───────────────────────────────────────────────────────────────

def fetch_raw_news(query: str) -> Tuple[Optional[List[Dict]], str]:
    """
    Fetch up to 5 news articles for the query.
    Falls back to web search if NewsAPI returns nothing.

    Returns:
        (articles, topic) on success
        (None, error_message) on total failure
    """
    if not config.NEWS_API_KEY:
        return None, "NEWS_API_KEY is not configured."

    topic = extract_topic(query)

    try:
        if topic in VALID_CATEGORIES:
            url    = "https://newsapi.org/v2/top-headlines"
            params = {
                "category": topic,
                "country":  "us",
                "pageSize": 5,
                "apiKey":   config.NEWS_API_KEY,
            }
        else:
            url    = "https://newsapi.org/v2/everything"
            params = {
                "q":        topic,
                "language": "en",
                "sortBy":   "publishedAt",
                "pageSize": 5,
                "apiKey":   config.NEWS_API_KEY,
            }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            log.warning("NewsAPI error for '%s': %s", topic, data.get("message"))
            return _web_search_fallback(topic)

        articles = data.get("articles", [])
        if not articles:
            log.info("NewsAPI: no articles for '%s', trying web search fallback", topic)
            return _web_search_fallback(topic)

        cleaned = []
        for article in articles:
            title       = _clean_text(article.get("title", ""))
            description = _clean_text(article.get("description", ""))
            source      = article.get("source", {}).get("name", "")
            published   = article.get("publishedAt", "")[:10]
            url_link    = article.get("url", "")

            if title:
                cleaned.append({
                    "title":       title,
                    "description": description,
                    "source":      source,
                    "published":   published,
                    "url":         url_link,
                })

        return cleaned, topic

    except requests.Timeout:
        log.warning("NewsAPI timed out for '%s', trying web search fallback", topic)
        return _web_search_fallback(topic)
    except requests.RequestException as exc:
        log.error("NewsAPI request failed: %s", exc)
        return _web_search_fallback(topic)
    except Exception as exc:
        log.exception("Unexpected news error")
        return None, f"Unexpected error: {exc}"
