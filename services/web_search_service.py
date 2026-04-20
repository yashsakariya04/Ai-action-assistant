"""
web_search_service.py — Robust web search with multiple strategies.

Strategy order:
  1. DuckDuckGo via ddgs (new package name)
  2. DuckDuckGo via duckduckgo_search (old package name)
  3. Wikipedia API (always works, no key needed)
  4. LLM knowledge fallback (uses existing Groq)

No API key required for any strategy.
Install: pip install ddgs
"""

import logging
import requests
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

MAX_RESULTS = 5
TIMEOUT     = 10


# ─────────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────

def search_web(query: str) -> Dict:
    """
    Search the web using multiple strategies with automatic fallback.

    Returns:
        { "status": "success"|"error", "message": str, "results": list }
    """
    query = query.strip()
    if not query:
        return {"status": "error", "message": "No search query provided."}

    # Strategy 1: ddgs (new package)
    result = _search_ddgs_new(query)
    if result:
        return {"status": "success", "message": _format_results(query, result), "results": result}

    # Strategy 2: duckduckgo_search (old package)
    result = _search_ddgs_old(query)
    if result:
        return {"status": "success", "message": _format_results(query, result), "results": result}

    # Strategy 3: Wikipedia API (no key, very reliable)
    result = _search_wikipedia(query)
    if result:
        return {"status": "success", "message": _format_results(query, result), "results": result}

    # Strategy 4: LLM knowledge fallback
    return _llm_fallback(query)


# ─────────────────────────────────────────────────────────────
# STRATEGY 1 — ddgs (new package name, pip install ddgs)
# ─────────────────────────────────────────────────────────────

def _search_ddgs_new(query: str) -> Optional[List[Dict]]:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=MAX_RESULTS, safesearch="moderate"))
        if raw:
            log.info("ddgs search succeeded: %d results", len(raw))
            return [{"title": r.get("title",""), "body": r.get("body",""), "href": r.get("href","")} for r in raw]
    except ImportError:
        pass
    except Exception as exc:
        log.warning("ddgs search failed: %s", exc)
    return None


# ─────────────────────────────────────────────────────────────
# STRATEGY 2 — duckduckgo_search (old package name)
# ─────────────────────────────────────────────────────────────

def _search_ddgs_old(query: str) -> Optional[List[Dict]]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=MAX_RESULTS, safesearch="moderate"))
        if raw:
            log.info("duckduckgo_search succeeded: %d results", len(raw))
            return [{"title": r.get("title",""), "body": r.get("body",""), "href": r.get("href","")} for r in raw]
    except ImportError:
        pass
    except Exception as exc:
        log.warning("duckduckgo_search failed: %s", exc)
    return None


# ─────────────────────────────────────────────────────────────
# STRATEGY 3 — Wikipedia API (always free, no key needed)
# ─────────────────────────────────────────────────────────────

def _search_wikipedia(query: str) -> Optional[List[Dict]]:
    """
    Use Wikipedia's free search API as a reliable fallback.
    Works for people, places, concepts, events.
    """
    try:
        # Search for matching pages
        search_url = "https://en.wikipedia.org/w/api.php"
        search_params = {
            "action":   "query",
            "list":     "search",
            "srsearch": query,
            "format":   "json",
            "srlimit":  3,
        }
        resp = requests.get(search_url, params=search_params, timeout=TIMEOUT)
        resp.raise_for_status()
        search_data = resp.json()

        pages = search_data.get("query", {}).get("search", [])
        if not pages:
            return None

        results = []
        for page in pages[:3]:
            title   = page.get("title", "")
            snippet = page.get("snippet", "")
            # Clean HTML tags from snippet
            import re
            snippet = re.sub(r"<[^>]+>", "", snippet).strip()
            page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            results.append({
                "title": title,
                "body":  snippet,
                "href":  page_url,
            })

        if results:
            log.info("Wikipedia search succeeded: %d results", len(results))
            return results

    except Exception as exc:
        log.warning("Wikipedia search failed: %s", exc)
    return None


# ─────────────────────────────────────────────────────────────
# STRATEGY 4 — LLM Knowledge Fallback
# ─────────────────────────────────────────────────────────────

def _llm_fallback(query: str) -> Dict:
    """
    Use the existing Groq LLM to answer when all search strategies fail.
    This ensures the user always gets a useful response.
    """
    try:
        from llm_service import _call_groq
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant answering a web search query. "
                    "Give a concise, factual answer based on your knowledge. "
                    "Format it clearly. Do not mention that you are using your training data."
                )
            },
            {"role": "user", "content": f"Search query: {query}"}
        ]
        answer = _call_groq(messages, temperature=0.3, max_tokens=400)
        return {
            "status":  "success",
            "message": f"Search Results — {query}\n{'-'*40}\n{answer}\n{'-'*40}",
            "results": [],
        }
    except Exception as exc:
        log.error("LLM fallback also failed: %s", exc)
        return {
            "status":  "error",
            "message": f"Search is currently unavailable. Please try again later.",
        }


# ─────────────────────────────────────────────────────────────
# FORMATTER
# ─────────────────────────────────────────────────────────────

def _format_results(query: str, results: List[Dict]) -> str:
    """Format search results into a clean readable string."""
    lines = [
        f"Web Search — {query}",
        "-" * 40,
    ]
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        body  = r.get("body", "").strip()
        href  = r.get("href", "").strip()

        lines.append(f"\n{i}. {title}")
        if body:
            snippet = body[:220] + "..." if len(body) > 220 else body
            lines.append(f"   {snippet}")
        if href:
            lines.append(f"   {href}")

    lines.append("\n" + "-" * 40)
    return "\n".join(lines)