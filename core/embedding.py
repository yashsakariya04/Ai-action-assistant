"""
embedding.py — Text embeddings via Google Gemini API (text-embedding-004).

Free tier: 1,500 requests/minute, 1,500,000 tokens/minute.
Dimension: 768 (task_type=RETRIEVAL_DOCUMENT / RETRIEVAL_QUERY).
No local model loaded — zero RAM overhead.

Fallback: if GEMINI_API_KEY is not set, raises a clear EnvironmentError.
"""

import logging
import os
from typing import List

from google import genai
from google.genai import types

log = logging.getLogger(__name__)

_EMBED_MODEL = "models/text-embedding-004"
_client: genai.Client | None = None


def _ensure_configured():
    global _client
    if _client:
        return
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. "
            "Get a free key at https://aistudio.google.com/app/apikey"
        )
    _client = genai.Client(api_key=api_key)
    log.info("Gemini embedding configured (model: %s)", _EMBED_MODEL)


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks for indexing."""
    chunks, start = [], 0
    length = len(text)
    while start < length:
        end   = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = end - overlap
    return chunks


def generate_embeddings(texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT") -> List[List[float]]:
    """
    Embed a list of strings using Gemini text-embedding-004.

    Args:
        texts:     Strings to embed.
        task_type: "RETRIEVAL_DOCUMENT" for indexing, "RETRIEVAL_QUERY" for queries.

    Returns:
        List of float vectors (768-dim each).
    """
    if not texts:
        return []

    _ensure_configured()

    all_embeddings = []
    for i in range(0, len(texts), 100):
        batch = texts[i:i + 100]
        result = _client.models.embed_content(
            model=_EMBED_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(task_type=task_type),
        )
        all_embeddings.extend(e.values for e in result.embeddings)
    return all_embeddings
