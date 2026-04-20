"""
vector_store.py — ChromaDB wrapper for knowledge-base storage and retrieval.
"""

import uuid
import logging
from typing import Optional, List, Dict

import chromadb

import config

log = logging.getLogger(__name__)

_client:     Optional[chromadb.PersistentClient] = None
_collection: Optional[chromadb.Collection]       = None

COLLECTION_NAME = "knowledge_base"


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=config.CHROMA_DB_DIR)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        log.info("ChromaDB collection '%s' ready (%d docs).",
                 COLLECTION_NAME, _collection.count())
    return _collection


def store_documents(chunks: List[str], embeddings: List[List[float]]) -> int:
    """
    Add document chunks to the vector store.

    Returns:
        Number of chunks stored.
    """
    if not chunks:
        return 0

    collection = _get_collection()
    ids        = [str(uuid.uuid4()) for _ in chunks]

    collection.add(ids=ids, documents=chunks, embeddings=embeddings)
    log.info("Stored %d chunks in knowledge base.", len(chunks))
    return len(chunks)


def query_similar(
    query_embedding: List[float],
    top_k: int = 3,
) -> List[Dict]:
    """
    Retrieve the most similar document chunks.

    Returns:
        List of dicts: {"document": str, "score": float}
        Sorted by ascending distance (most similar first).
        Empty list if the collection is empty.
    """
    collection = _get_collection()

    if collection.count() == 0:
        return []

    n = min(top_k, collection.count())
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n,
        include=["documents", "distances"],
    )

    documents = results["documents"][0]
    distances = results["distances"][0]

    return [
        {"document": doc, "score": dist}
        for doc, dist in zip(documents, distances)
    ]


def collection_count() -> int:
    """Return the number of documents currently stored."""
    return _get_collection().count()
