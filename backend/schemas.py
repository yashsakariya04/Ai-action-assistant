"""
schemas.py — Request and response models for the /chat endpoint.
"""

from typing import Optional, List
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # client-provided; server generates if absent


class NewsArticle(BaseModel):
    title: str
    description: Optional[str] = None
    source: str
    published: str
    url: Optional[str] = None


class ChatResponse(BaseModel):
    status: str                                        # success | pending | awaiting | cancelled | error
    action: str                                        # email | calendar | news | rag | weather | none
    message: str                                       # always present
    session_id: Optional[str] = None                  # echoed back so client can persist it
    preview: Optional[dict] = None                    # only when status == "awaiting"
    news_articles: Optional[List[NewsArticle]] = None # only when action == "news"
