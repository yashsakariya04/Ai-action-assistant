"""
ingestion.py — Web content fetching and text extraction for RAG indexing.
"""

import logging
import re
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

import config
from core.embedding import chunk_text, generate_embeddings
from core.vector_store import store_documents

log = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "RAG Knowledge Bot/1.0 (educational project)"}


def fetch_url_content(url: str) -> str:
    try:
        response = requests.get(url, headers=_HEADERS, timeout=20)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Failed to fetch URL '{url}': {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    content_div = soup.find("div", {"id": "mw-content-text"})
    text = content_div.get_text(separator=" ") if content_div else soup.get_text(separator=" ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ingest_urls(urls: Optional[List[str]] = None) -> int:
    urls  = urls or config.DEFAULT_URLS
    total = 0
    for url in urls:
        try:
            log.info("Ingesting: %s", url)
            text       = fetch_url_content(url)
            chunks     = chunk_text(text)
            embeddings = generate_embeddings(chunks)
            stored     = store_documents(chunks, embeddings)
            total     += stored
            log.info("  → %d chunks from %s", stored, url)
        except Exception as exc:
            log.error("Failed to ingest '%s': %s", url, exc)
    return total
