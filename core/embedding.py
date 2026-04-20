"""
embedding.py — Singleton SentenceTransformer model with text chunking.
"""

import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

log = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        log.info("Loading embedding model: %s", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """
    Split text into overlapping chunks for indexing.

    Args:
        text:       Source text.
        chunk_size: Maximum characters per chunk.
        overlap:    Character overlap between consecutive chunks.

    Returns:
        List of non-empty string chunks.
    """
    chunks = []
    start  = 0
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


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Encode a list of strings into embedding vectors.

    Args:
        texts: List of strings to embed.

    Returns:
        List of float vectors (one per input string).
    """
    if not texts:
        return []
    model   = _get_model()
    vectors = model.encode(texts, show_progress_bar=False, batch_size=64)
    return [v.tolist() for v in vectors]
