"""
db/models.py — SQLAlchemy ORM models.

Tables:
  users         — email + hashed password + profile
  sessions      — chat sessions per user
  messages      — individual messages per session
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, ForeignKey, Integer
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email      = Column(String(255), unique=True, nullable=False, index=True)
    password   = Column(String(255), nullable=False)
    name       = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    bio        = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    is_active  = Column(Boolean, default=True)

    sessions      = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    google_token  = relationship("GoogleToken", back_populates="user", uselist=False, cascade="all, delete-orphan")


class GoogleToken(Base):
    """Stores per-user Google OAuth2 token (pickled Credentials object)."""
    __tablename__ = "google_tokens"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    token_data = Column(Text, nullable=False)   # base64-encoded pickle
    email      = Column(String(255), nullable=True)  # Google account email
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    user = relationship("User", back_populates="google_token")


class ChatSession(Base):
    __tablename__ = "sessions"

    id         = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id    = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title      = Column(String(200), default="New Conversation")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    user       = relationship("User", back_populates="sessions")
    messages   = relationship("Message", back_populates="session", cascade="all, delete-orphan",
                              order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role       = Column(String(20), nullable=False)   # "user" | "assistant"
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    session    = relationship("ChatSession", back_populates="messages")
