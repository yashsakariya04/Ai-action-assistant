"""
session_store.py — DB-backed session management.

Each ChatSession row maps to one conversation.
Messages are persisted in the messages table.
An in-memory ConversationMemory is kept alive for the duration of the
process (for fast LLM context) and rebuilt from DB on first access.
"""

import logging
import threading
from sqlalchemy.orm import Session as DBSession

from core.memory_manager import ConversationMemory
from db.models import ChatSession, Message

log = logging.getLogger(__name__)


class Session:
    """Runtime session — wraps DB row + in-memory LLM memory buffer."""

    def __init__(self, session_id: str, db: DBSession):
        self.id                    = session_id
        self.memory                = ConversationMemory(max_buffer_turns=10)
        self.awaiting_confirmation = False
        self._db                   = db
        self._loaded               = False

    def _ensure_loaded(self):
        """Lazy-load last N messages from DB into memory buffer."""
        if self._loaded:
            return
        self._loaded = True
        rows = (
            self._db.query(Message)
            .filter(Message.session_id == self.id)
            .order_by(Message.created_at.desc())
            .limit(20)
            .all()
        )
        for row in reversed(rows):
            self.memory.add(row.role, row.content)

    def persist_message(self, role: str, content: str):
        """Save a message to the DB."""
        msg = Message(session_id=self.id, role=role, content=content)
        self._db.add(msg)
        self._db.commit()

    def reset(self):
        self.memory.reset()
        self.awaiting_confirmation = False
        # Delete messages from DB
        self._db.query(Message).filter(Message.session_id == self.id).delete()
        self._db.commit()
        self._loaded = False


# ── In-process cache (avoids re-querying DB on every request) ─
_cache: dict[str, Session] = {}
_lock  = threading.Lock()


def get_session(session_id: str, db: DBSession, user_id: str | None = None) -> Session:
    """
    Return a Session for session_id.
    Creates the DB row if it doesn't exist (requires user_id on first call).
    """
    with _lock:
        if session_id in _cache:
            session = _cache[session_id]
            session._db = db          # refresh DB handle per request
            session._ensure_loaded()
            return session

    # Check / create DB row
    row = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if row is None:
        if not user_id:
            raise ValueError("user_id required to create a new session")
        row = ChatSession(id=session_id, user_id=user_id)
        db.add(row)
        db.commit()
        log.info("New DB session: %s (user=%s)", session_id, user_id)

    session = Session(session_id, db)
    session._ensure_loaded()

    with _lock:
        _cache[session_id] = session
    return session


def reset_session(session_id: str, db: DBSession) -> None:
    with _lock:
        if session_id in _cache:
            _cache[session_id].reset()
        else:
            db.query(Message).filter(Message.session_id == session_id).delete()
            db.commit()


def session_count() -> int:
    with _lock:
        return len(_cache)


def get_user_sessions(user_id: str, db: DBSession) -> list[dict]:
    """Return all sessions for a user, newest first."""
    rows = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(50)
        .all()
    )
    return [{"session_id": r.id, "title": r.title, "updated_at": r.updated_at.isoformat()} for r in rows]


def update_session_title(session_id: str, title: str, db: DBSession) -> None:
    db.query(ChatSession).filter(ChatSession.id == session_id).update({"title": title})
    db.commit()
