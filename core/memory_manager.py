"""
memory_manager.py — In-process conversation memory only.
No database. No embeddings. Pure in-memory buffer + rolling summary.
Resets when the server restarts.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

log = logging.getLogger(__name__)


class ConversationMemory:
    """
    Smart in-memory conversation context.
    
    - Keeps a rolling buffer of the last N turns (full messages).
    - When buffer exceeds the limit, oldest turns are summarised into
      a compact text block and dropped from the buffer.
    - The summary + recent buffer is what gets passed to the LLM.
    - Pending action scratchpad for multi-turn field collection.
    - Everything lives in RAM — clears on restart.
    """

    def __init__(self, max_buffer_turns: int = 10, compress_threshold: int = 30):
        self.max_buffer_turns  = max_buffer_turns
        self.compress_threshold = compress_threshold  # min messages before compression fires
        self._buffer: List[Dict] = []   # list of {"role": str, "content": str}
        self._summary: str       = ""   # compressed summary of older turns
        self.pending_action: Optional[Dict] = None

    # ── BUFFER ────────────────────────────────────────────────

    def add(self, role: str, content: str) -> None:
        """Add one turn. Compress oldest half only after compress_threshold messages."""
        self._buffer.append({"role": role, "content": content})
        if (len(self._buffer) > self.max_buffer_turns * 2
                and len(self._buffer) >= self.compress_threshold):
            self._compress()

    def get_buffer(self) -> List[Dict]:
        """Return recent turns as list of {role, content} dicts for LLM history."""
        return list(self._buffer)

    def get_context_block(self) -> str:
        """
        Return the full conversation context as a single string.
        Used to inject into RAG / general queries.
        """
        parts = []
        if self._summary:
            parts.append(f"[Earlier conversation summary]\n{self._summary}")
        if self._buffer:
            recent = "\n".join(
                f"{m['role'].upper()}: {m['content']}"
                for m in self._buffer[-6:]  # last 3 exchanges
            )
            parts.append(f"[Recent conversation]\n{recent}")
        return "\n\n".join(parts)

    # ── COMPRESSION ───────────────────────────────────────────

    def _compress(self) -> None:
        """Summarise the oldest half of the buffer using the LLM."""
        from core.llm_service import _call_light

        half = len(self._buffer) // 2
        old  = self._buffer[:half]
        self._buffer = self._buffer[half:]

        text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in old)
        prompt = [
            {"role": "system", "content": (
                "You are summarising a conversation. "
                "Write a concise factual summary preserving key decisions, "
                "names, emails, dates and any confirmed actions. "
                "Be brief. Plain text only."
            )},
            {"role": "user", "content": text},
        ]
        try:
            update = _call_light(prompt, max_tokens=200, temperature=0.0)  # summary needs no 120B model
            self._summary = (self._summary + "\n" + update).strip() if self._summary else update
            log.info("Buffer compressed. Summary: %d chars.", len(self._summary))
        except Exception as exc:
            log.warning("Compression failed: %s", exc)

    # ── PENDING ACTION SCRATCHPAD ─────────────────────────────

    def set_pending_action(self, plan: Dict) -> None:
        self.pending_action = plan

    def clear_pending_action(self) -> None:
        self.pending_action = None

    def merge_action_arguments(self, new_plan: Dict) -> Dict:
        """
        Merge new extracted fields into the existing pending action.
        - No pending action  → return new plan as-is
        - rag incoming + real pending  → keep pending (follow-up info)
        - Different real action  → replace entirely
        - Same action  → merge non-null fields
        """
        PASSTHROUGH = {"rag"}

        if not self.pending_action:
            return new_plan

        pending_type  = self.pending_action.get("action")
        incoming_type = new_plan.get("action")

        if incoming_type not in PASSTHROUGH and incoming_type != pending_type:
            self.pending_action = new_plan
            return new_plan

        if incoming_type in PASSTHROUGH and pending_type not in PASSTHROUGH:
            return self.pending_action

        # Same action — merge non-null fields
        existing = dict(self.pending_action.get("arguments", {}))
        for k, v in new_plan.get("arguments", {}).items():
            if v is not None:
                existing[k] = v
        self.pending_action["arguments"] = existing
        return self.pending_action

    def reset(self) -> None:
        self._buffer.clear()
        self._summary = ""
        self.pending_action = None

    # Keep HybridMemory name available as alias for backward compat
    get_summary = lambda self: self._summary
    retrieve_relevant = lambda self, q, top_k=3: []
    store_long_term   = lambda self, role, content: None


# Alias so existing imports still work
HybridMemory = ConversationMemory
