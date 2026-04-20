"""
rag_pipeline.py — RAG pipeline using KB + in-memory conversation context.
Now includes source attribution so users know where answers come from.
"""

import logging
from typing import List, Optional

import config
from core.embedding import generate_embeddings
from core.vector_store import query_similar, collection_count
from core.llm_service import get_llm_response

log = logging.getLogger(__name__)


def initialize_knowledge_base(urls: Optional[List[str]] = None) -> None:
    """Ingest default URLs into KB if empty. Safe to call multiple times."""
    if collection_count() > 0:
        log.info("Knowledge base ready (%d docs).", collection_count())
        return
    log.info("Knowledge base empty. Starting ingestion...")
    from core.ingestion import ingest_urls
    total = ingest_urls(urls or config.DEFAULT_URLS)
    log.info("Ingestion complete. %d chunks stored.", total)


def run_rag(query: str, memory) -> str:
    """
    Answer a general query using:
    1. KB vector search (if relevant chunks found)
    2. In-memory conversation context (summary + recent buffer)
    3. LLM general knowledge as fallback

    """
    # 1. Search KB for relevant chunks
    knowledge_context = ""
    kb_used = False

    try:
        query_embedding = generate_embeddings([query])[0]
        kb_results = query_similar(query_embedding, top_k=5)
        relevant = [r for r in kb_results if r["score"] < config.SIMILARITY_THRESHOLD]

        if relevant:
            knowledge_context = "\n\n".join(r["document"] for r in relevant)
            kb_used = True
            log.info(
                "KB search: %d relevant chunks (best score: %.3f)",
                len(relevant),
                relevant[0]["score"],
            )
        else:
            log.info(
                "KB search: no relevant chunks found (threshold: %.2f)",
                config.SIMILARITY_THRESHOLD,
            )
    except Exception as exc:
        log.warning("KB search failed: %s", exc)

    # 2. Build context: KB chunks + conversation history
    context_parts = []
    if knowledge_context:
        context_parts.append("Knowledge Base:\n" + knowledge_context)

    conv_context = memory.get_context_block()
    if conv_context:
        context_parts.append(conv_context)

    context = "\n\n".join(context_parts)

    # 3. Generate response
    # Use PRIMARY tier only when KB context found (quality matters).
    # Use LIGHT tier for pure conversation (saves primary token budget).
    from core.llm_service import _call_primary, _call_light
    now_str = __import__('datetime').datetime.now().strftime("%A, %B %d %Y at %I:%M %p")
    from core.llm_service import BASE_SYSTEM_PROMPT
    system = BASE_SYSTEM_PROMPT.format(datetime=now_str)
    if context:
        system += "\n\nCONTEXT (use this to answer):\n" + context

    msgs = [{"role": "system", "content": system}]
    history = memory.get_buffer()
    if history:
        msgs.extend(history[-10:])
    msgs.append({"role": "user", "content": query})

    response = _call_primary(msgs, temperature=0.6, max_tokens=1200) if kb_used \
               else _call_light(msgs, temperature=0.6, max_tokens=1200)

    # 4. Store in memory buffer
    memory.add("user", query)
    memory.add("assistant", response)

    return response