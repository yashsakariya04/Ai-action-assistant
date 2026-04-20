"""
mcp_server.py — AI Action Assistant MCP Server

ARCHITECTURE: 1 Master Brain + 7 Dedicated Service Tools + 2 Utilities

TOOL DESIGN PHILOSOPHY:
  The 'chat' tool is the MASTER BRAIN — it understands natural language,
  auto-routes to the correct service, and handles multi-turn conversations.
  Use it for everything unless you need direct service control.

  Each dedicated service tool gives MCP clients (Claude Desktop, Cursor, etc.)
  explicit, single-purpose access to one capability. They all share the same
  session state and flow through the same Planner→Validator→Executor pipeline.

TOOLS:
  MASTER:
    chat()               — Universal brain: RAG + auto-routing to all services

  DEDICATED SERVICES:
    weather_service()    — Current weather for any city
    web_search_service() — Search the internet (DuckDuckGo + Wikipedia fallback)
    summarizer_service() — Summarize URLs, uploaded files, or raw text
    email_service()      — Draft, preview, and send emails via Gmail API
    calendar_service()   — Schedule Google Calendar events
    news_service()       — Fetch live news headlines on any topic

  UTILITIES:
    reset_conversation() — Clear session memory and pending actions
    get_system_status()  — Health check for all services

RESOURCES:
    config://settings    — Current configuration
    kb://status          — Knowledge base document count
    help://guide         — Full usage guide

PROMPTS:
    compose_email()      — Start email workflow
    schedule_event()     — Start calendar workflow
    search_web()         — Start web search
    get_weather()        — Get weather for a city
    summarize_url()      — Summarize a URL
    get_news()           — Get news on a topic
    ask_question()       — Ask anything via RAG

SESSION: All tools share a single in-memory session. Multi-turn workflows
         work naturally across any tool combination.
"""

import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# MCP SERVER INSTANCE
# ─────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="AI Action Assistant",
    instructions=(
        "A powerful personal AI assistant that executes real-world tasks.\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "MASTER TOOL (use this for everything by default)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "chat(message) — The master brain. Understands natural language\n"
        "  and automatically routes to the right service. Examples:\n"
        "  - 'what is the weather in Mumbai?' → weather\n"
        "  - 'search for latest AI news' → web search\n"
        "  - 'summarize https://example.com' → summarizer\n"
        "  - 'send email to John about the meeting' → email\n"
        "  - 'schedule a meeting next Monday at 10am' → calendar\n"
        "  - 'latest tech news' → news\n"
        "  - 'what is machine learning?' → RAG knowledge base\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "DEDICATED SERVICE TOOLS (for explicit direct control)\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "weather_service(city)         — Current weather for a city\n"
        "web_search_service(query)     — Search the internet\n"
        "summarizer_service(...)       — Summarize URL / text / file path\n"
        "email_service(message)        — Full email workflow\n"
        "calendar_service(message)     — Full calendar workflow\n"
        "news_service(topic)           — Live news headlines\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "UTILITY TOOLS\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "reset_conversation()          — Clear memory, start fresh\n"
        "get_system_status()           — Check all services health\n\n"

        "SAFETY RULES:\n"
        "- Email addresses are NEVER fabricated — user must provide them\n"
        "- Calendar dates must be real and in the future\n"
        "- Emails and calendar events require explicit confirmation before execution\n"
        "- Weather, search, summarize, and news execute immediately (read-only)\n\n"

        "MULTI-TURN: All tools share session state. Send follow-up messages\n"
        "to continue any workflow naturally."
    ),
)


# ─────────────────────────────────────────────────────────────
# SHARED HELPER — Format ChatResponse for MCP clients
# ─────────────────────────────────────────────────────────────

def _format_response(response) -> str:
    """Convert a ChatResponse into a clean formatted string for MCP clients."""
    status_line = f"[{response.status.upper()} | {response.action.upper()}]"
    result      = f"{status_line}\n{'-' * 60}\n{response.message}"

    # Append structured news articles if present
    if response.news_articles:
        result += "\n\nArticles:\n"
        for i, a in enumerate(response.news_articles, 1):
            result += f"  {i}. {a.title}"
            if a.description:
                result += f"\n     {a.description}"
            result += f"\n     {a.source} | {a.published}\n"

    # Add actionable next-step hints
    if response.status == "pending":
        result += "\n\n→ Provide the requested information to continue."
    elif response.status == "awaiting":
        result += "\n\n→ Reply 'yes' to confirm, 'no' to cancel, or describe changes."
    elif response.status == "error":
        result += "\n\n→ Please check the error above and try again."

    return result


def _get_session():
    """Get or create the MCP server's dedicated session."""
    from backend.session_store import get_session
    return get_session("mcp-server")


def _process(message: str, file_path: str = None) -> str:
    """Run a message through the chat engine and return formatted result."""
    from backend.chat_engine import process
    session  = _get_session()
    response = process(message, session, file_path=file_path)
    return _format_response(response)


# ═════════════════════════════════════════════════════════════
# MASTER BRAIN TOOL
# ═════════════════════════════════════════════════════════════

@mcp.tool()
def chat(message: str) -> str:
    """
    Master brain — handles ALL types of conversations and tasks.

    This is the recommended tool for all interactions. It understands
    natural language and automatically routes to the correct service.

    CAPABILITIES (all handled automatically):
      General questions    → answered via RAG knowledge base
      Weather queries      → "what is the weather in Delhi?"
      Web search           → "search for latest iPhone reviews"
      Summarization        → "summarize https://example.com"
      Email sending        → "send email to John about the project"
      Calendar scheduling  → "schedule a meeting next Friday at 2pm"
      News fetching        → "latest AI news"
      Casual conversation  → "hello", "what can you do?"

    MULTI-TURN WORKFLOWS:
      After starting an email or calendar task, use chat() to:
        - Provide missing info:  "john@company.com"
        - Modify content:        "change the subject to Project Update"
        - Confirm execution:     "yes" / "send it" / "looks good"
        - Cancel:                "no" / "cancel"

    STATUS CODES IN RESPONSE:
      [SUCCESS | RAG]       — question answered from knowledge base
      [SUCCESS | WEATHER]   — weather data returned
      [SUCCESS | WEB_SEARCH]— search results returned
      [SUCCESS | SUMMARIZE] — content summarized
      [SUCCESS | EMAIL]     — email sent
      [SUCCESS | CALENDAR]  — calendar event created
      [SUCCESS | NEWS]      — news articles returned
      [PENDING | ...]       — asking for missing information
      [AWAITING | ...]      — showing preview, needs confirmation
      [CANCELLED | ...]     — action was cancelled
      [ERROR | ...]         — something went wrong

    Args:
        message: Any natural language input — question, task request,
                 follow-up, confirmation, or casual conversation.

    Returns:
        Formatted response with status code and content.
    """
    return _process(message)


# ═════════════════════════════════════════════════════════════
# DEDICATED SERVICE TOOLS
# ═════════════════════════════════════════════════════════════

@mcp.tool()
def weather_service(city: str) -> str:
    """
    Get current weather for any city in the world.

    Returns temperature, feels-like, humidity, wind speed, and visibility.
    Executes immediately — no confirmation needed.

    Examples:
      weather_service("Mumbai")
      weather_service("London")
      weather_service("New York")
      weather_service("Tokyo")

    Args:
        city: Name of the city to get weather for.

    Returns:
        Formatted weather report with current conditions.
    """
    from services.weather_service import fetch_weather

    if not city or not city.strip():
        return "[ERROR | WEATHER]\n----------------------------------------\nPlease provide a city name."

    result = fetch_weather(city.strip())

    if result["status"] == "success":
        return f"[SUCCESS | WEATHER]\n{'-' * 60}\n{result['message']}"
    return f"[ERROR | WEATHER]\n{'-' * 60}\n{result['message']}"


@mcp.tool()
def web_search_service(query: str) -> str:
    """
    Search the internet for any topic, person, event, or question.

    Uses DuckDuckGo with Wikipedia and LLM fallback strategies.
    Executes immediately — no confirmation needed.

    Examples:
      web_search_service("latest developments in quantum computing")
      web_search_service("Elon Musk net worth 2025")
      web_search_service("Python FastAPI tutorial")
      web_search_service("best restaurants in Ahmedabad")

    Args:
        query: Search query — any topic or question.

    Returns:
        Top search results with titles, snippets, and source URLs.
    """
    from services.web_search_service import search_web

    if not query or not query.strip():
        return "[ERROR | WEB_SEARCH]\n----------------------------------------\nPlease provide a search query."

    result = search_web(query.strip())

    if result["status"] == "success":
        return f"[SUCCESS | WEB_SEARCH]\n{'-' * 60}\n{result['message']}"
    return f"[ERROR | WEB_SEARCH]\n{'-' * 60}\n{result['message']}"


@mcp.tool()
def summarizer_service(
    url: str = "",
    text: str = "",
    file_path: str = "",
) -> str:
    """
    Summarize content from a URL, raw text, or a file path.

    Provide exactly ONE of: url, text, or file_path.
    Executes immediately — no confirmation needed.

    SUMMARIZE A URL:
      summarizer_service(url="https://en.wikipedia.org/wiki/Artificial_intelligence")
      summarizer_service(url="https://techcrunch.com/some-article")

    SUMMARIZE RAW TEXT:
      summarizer_service(text="The quick brown fox... [long text here]")

    SUMMARIZE A FILE (provide server-side path):
      summarizer_service(file_path="/tmp/uploads/document.pdf")
      summarizer_service(file_path="/tmp/uploads/report.docx")

    SUPPORTED FILE TYPES: PDF, DOCX, XLSX, TXT

    Args:
        url:       Full URL starting with http:// or https://
        text:      Raw text content to summarize (paste directly)
        file_path: Absolute path to an uploaded file on the server

    Returns:
        A structured summary with key points and conclusion.
    """
    from services.summarizer_service import summarize

    # Validate at least one source is provided
    if not url.strip() and not text.strip() and not file_path.strip():
        return (
            "[ERROR | SUMMARIZE]\n"
            f"{'-' * 60}\n"
            "Please provide one of:\n"
            "  - url='https://...'\n"
            "  - text='your text here'\n"
            "  - file_path='/path/to/file.pdf'"
        )

    result = summarize(
        content=text.strip(),
        url=url.strip(),
        file_path=file_path.strip(),
    )

    return f"[SUCCESS | SUMMARIZE]\n{'-' * 60}\n{result}"


@mcp.tool()
def email_service(message: str) -> str:
    """
    Full email workflow — draft, preview, and send emails via Gmail API.

    Handles the complete multi-turn email workflow through conversation.
    Requires explicit confirmation before sending — nothing goes out automatically.

    STARTING A NEW EMAIL:
      "send a congratulations email to Ravi for his promotion"
      "email the team about tomorrow's meeting cancellation"
      "write a follow-up to the client about the proposal"

    PROVIDING MISSING INFORMATION (when asked):
      "ravi.sharma@company.com"          ← providing email address
      "his email is john@example.com"    ← providing email address

    MODIFYING BEFORE SENDING:
      "change the subject to 'Important Update'"
      "make the tone more formal"
      "add a line about the deadline"

    CONFIRMING OR CANCELLING:
      "yes" / "send it" / "looks good"  ← sends the email
      "no" / "cancel" / "don't send"    ← cancels

    SAFETY GUARANTEES:
      - Email addresses MUST come from you — never invented by AI
      - Full email body shown for review before sending
      - Nothing is sent without your explicit confirmation

    Args:
        message: Natural language message at any stage of the email workflow.

    Returns:
        Response showing current state: missing info needed, preview, or result.
    """
    session = _get_session()

    # Smart routing: prepend email intent if no keyword found and not mid-workflow
    if (not session.awaiting_confirmation
            and not session.memory.pending_action
            and "@" not in message
            and message.lower().strip() not in ("yes", "no", "cancel", "ok", "sure")):
        if not any(w in message.lower() for w in
                   ("mail", "email", "send", "write to", "compose", "draft")):
            message = f"send an email: {message}"

    return _process(message)


@mcp.tool()
def calendar_service(message: str) -> str:
    """
    Full calendar workflow — schedule and create Google Calendar events.

    Handles the complete multi-turn scheduling workflow through conversation.
    Requires explicit confirmation before creating — nothing is created automatically.

    SCHEDULING AN EVENT:
      "schedule a team standup every Monday at 9am"
      "book a dentist appointment tomorrow at 2pm"
      "create a birthday party event this Saturday at 6pm"
      "add a project review meeting next Friday at 3pm for 2 hours"

    PROVIDING MISSING INFORMATION (when asked):
      "the title is Quarterly Review"
      "make it 2 hours"
      "location is Conference Room A"
      "add a description about Q4 goals"

    MODIFYING BEFORE CREATING:
      "change the time to 4pm"
      "make it an all-day event"

    CONFIRMING OR CANCELLING:
      "yes" / "schedule it" / "create it"  ← creates the event
      "no" / "cancel"                      ← cancels

    SAFETY GUARANTEES:
      - Dates must be real and in the future — never fabricated
      - Full event details shown for review before creation
      - Nothing is created without your explicit confirmation

    Args:
        message: Natural language message at any stage of the calendar workflow.

    Returns:
        Response showing current state: missing info needed, preview, or result.
    """
    session = _get_session()

    # Smart routing: prepend calendar intent if no keyword found and not mid-workflow
    if (not session.awaiting_confirmation
            and not session.memory.pending_action
            and message.lower().strip() not in ("yes", "no", "cancel", "ok", "sure")):
        if not any(w in message.lower() for w in
                   ("schedule", "book", "calendar", "event", "meeting",
                    "appointment", "create", "add")):
            message = f"schedule a calendar event: {message}"

    return _process(message)


@mcp.tool()
def news_service(topic: str = "general") -> str:
    """
    Fetch the latest news headlines on any topic.

    Returns up to 5 recent articles with title, description, source, and date.
    Executes immediately — no confirmation needed.

    TOPIC EXAMPLES:
      news_service("technology")
      news_service("India cricket")
      news_service("artificial intelligence")
      news_service("business")
      news_service("Elon Musk")
      news_service()                 ← top general headlines

    VALID CATEGORIES (for top headlines by category):
      business, entertainment, general, health, science, sports, technology

    Args:
        topic: News topic, keyword, or category. Defaults to "general".

    Returns:
        Formatted list of news articles with source and publication date.
    """
    message = topic.strip() if topic.strip() else "general"

    # Ensure routing to news action
    if not any(w in message.lower() for w in ("news", "headlines", "latest")):
        message = f"get latest news about: {message}"

    return _process(message)


# ═════════════════════════════════════════════════════════════
# UTILITY TOOLS
# ═════════════════════════════════════════════════════════════

@mcp.tool()
def reset_conversation() -> str:
    """
    Reset the conversation — clears all memory and pending actions.

    Use this when:
      - Starting a completely new task
      - The assistant is stuck on old context
      - You want to cancel everything and start fresh
      - Switching between very different tasks

    This clears:
      - Conversation history and memory summary
      - Any pending email or calendar workflows
      - Awaiting confirmation state

    Returns:
        Confirmation that session has been reset.
    """
    from backend.session_store import reset_session
    reset_session("mcp-server")
    return (
        "[SUCCESS | RESET]\n"
        f"{'-' * 60}\n"
        "Session reset successfully.\n"
        "Memory cleared. Pending actions cancelled.\n"
        "Ready for a fresh conversation."
    )


@mcp.tool()
def get_system_status() -> str:
    """
    Check the health and configuration status of all services.

    Returns the status of:
      - LLM model (Groq)
      - Knowledge base (ChromaDB document count)
      - Email service (Gmail API)
      - Calendar service (Google OAuth)
      - News service (NewsAPI)
      - Weather service (OpenWeatherMap)
      - Web search service (DuckDuckGo)
      - Summarizer service

    Use this to verify everything is configured correctly before
    running important tasks.

    Returns:
        JSON with detailed status of all services.
    """
    import config
    from core.vector_store import collection_count

    kb_count   = collection_count()
    email_ok   = bool(config.EMAIL_USER)
    news_ok    = bool(config.NEWS_API_KEY)
    weather_ok = bool(getattr(config, "OPENWEATHER_API_KEY", ""))
    google_ok  = os.path.exists(config.GOOGLE_CREDENTIALS_FILE)
    token_ok   = os.path.exists(config.GOOGLE_TOKEN_FILE)

    status = {
        "status":  "healthy",
        "version": "2.0.0",
        "llm": {
            "provider": "Groq",
            "model":    config.GROQ_MODEL,
            "status":   "ready" if config.GROQ_API_KEY else "not configured",
        },
        "knowledge_base": {
            "documents": kb_count,
            "status":    "ready" if kb_count > 0 else "empty — run ingestion",
        },
        "services": {
            "email": {
                "type":   "Gmail API",
                "status": "ready" if email_ok else "not configured — check EMAIL_USER in .env",
            },
            "calendar": {
                "type":   "Google Calendar API",
                "credentials": "found" if google_ok else "missing credentials.json",
                "token":       "valid"  if token_ok  else "missing — run calendar_auth.py",
                "status":      "ready"  if (google_ok and token_ok) else "needs setup",
            },
            "news": {
                "type":   "NewsAPI",
                "status": "ready" if news_ok else "not configured — check NEWS_API_KEY in .env",
            },
            "weather": {
                "type":   "OpenWeatherMap",
                "status": "ready" if weather_ok else "not configured — check OPENWEATHER_API_KEY in .env",
            },
            "web_search": {
                "type":   "DuckDuckGo + Wikipedia fallback",
                "status": "ready — no API key required",
            },
            "summarizer": {
                "type":   "LLM-based (Groq)",
                "status": "ready — supports PDF, DOCX, XLSX, URL, text",
            },
            "rag": {
                "type":   "ChromaDB + Sentence Transformers",
                "status": "ready" if kb_count > 0 else "empty knowledge base",
            },
        },
        "calendar_timezone": config.CALENDAR_TIMEZONE,
    }

    return json.dumps(status, indent=2)


# ═════════════════════════════════════════════════════════════
# RESOURCES
# ═════════════════════════════════════════════════════════════

@mcp.resource("config://settings")
def get_config_settings() -> str:
    """Returns the current assistant configuration."""
    import config

    settings = {
        "llm_model":                   config.GROQ_MODEL,
        "calendar_timezone":           config.CALENDAR_TIMEZONE,
        "email_user":                  config.EMAIL_USER or "not configured",
        "email_configured":            bool(config.EMAIL_USER),
        "news_api_configured":         bool(config.NEWS_API_KEY),
        "weather_api_configured":      bool(getattr(config, "OPENWEATHER_API_KEY", "")),
        "google_credentials_present":  os.path.exists(config.GOOGLE_CREDENTIALS_FILE),
        "google_token_present":        os.path.exists(config.GOOGLE_TOKEN_FILE),
        "similarity_threshold":        config.SIMILARITY_THRESHOLD,
        "chroma_db_dir":               config.CHROMA_DB_DIR,
    }
    return json.dumps(settings, indent=2)


@mcp.resource("kb://status")
def get_kb_status() -> str:
    """Returns knowledge base health and document count."""
    from core.vector_store import collection_count

    count = collection_count()
    return json.dumps({
        "total_documents": count,
        "status":          "healthy" if count > 0 else "empty",
        "message": (
            f"Knowledge base contains {count} document chunks and is ready."
            if count > 0
            else "Knowledge base is empty. Run ingestion to populate it."
        ),
    }, indent=2)


@mcp.resource("help://guide")
def get_help_guide() -> str:
    """Returns the complete usage guide for all tools."""
    return json.dumps({
        "master_tool": {
            "name":        "chat",
            "description": "Universal brain — use for all natural language requests.",
            "examples": [
                "what is the weather in Mumbai?",
                "search for latest AI research papers",
                "summarize https://example.com",
                "send email to team about deadline",
                "schedule a meeting next Monday at 10am",
                "latest technology news",
                "what is machine learning?",
            ],
        },
        "dedicated_tools": {
            "weather_service": {
                "purpose":    "Current weather for any city",
                "input":      "city name (string)",
                "example":    "weather_service('Mumbai')",
                "confirms":   False,
            },
            "web_search_service": {
                "purpose":    "Search the internet",
                "input":      "search query (string)",
                "example":    "web_search_service('quantum computing 2025')",
                "confirms":   False,
            },
            "summarizer_service": {
                "purpose":    "Summarize URL, text, or file",
                "inputs":     "url | text | file_path (one required)",
                "examples": [
                    "summarizer_service(url='https://example.com')",
                    "summarizer_service(text='long text...')",
                    "summarizer_service(file_path='/tmp/uploads/doc.pdf')",
                ],
                "confirms":   False,
            },
            "email_service": {
                "purpose":    "Draft and send emails via Gmail API",
                "flow":       "describe → collect fields → LLM drafts → preview → confirm → send",
                "safety":     "Email addresses must come from user. Preview shown before send.",
                "confirms":   True,
            },
            "calendar_service": {
                "purpose":    "Schedule Google Calendar events",
                "flow":       "describe → collect fields → preview → confirm → create",
                "safety":     "Dates must be real and future. Preview shown before creation.",
                "confirms":   True,
            },
            "news_service": {
                "purpose":    "Live news headlines",
                "input":      "topic or category (optional)",
                "example":    "news_service('India cricket')",
                "confirms":   False,
            },
        },
        "utility_tools": {
            "reset_conversation": "Clear session memory and all pending workflows",
            "get_system_status":  "Check health of all services",
        },
        "confirmation_guide": {
            "confirm": ["yes", "ok", "sure", "send it", "create it", "do it", "looks good"],
            "cancel":  ["no", "cancel", "abort", "stop", "don't", "never mind"],
            "modify":  ["change the...", "update the...", "make it more...", "add..."],
        },
    }, indent=2)


# ═════════════════════════════════════════════════════════════
# PROMPTS — Quick-start templates for common tasks
# ═════════════════════════════════════════════════════════════

@mcp.prompt()
def compose_email(recipient: str, purpose: str) -> str:
    """Start an email workflow for a specific recipient and purpose."""
    return (
        f"Send a professional {purpose} email to {recipient}. "
        f"Draft it clearly, show me a full preview, and send it after I confirm."
    )


@mcp.prompt()
def schedule_event(title: str, when: str, duration_hours: int = 1) -> str:
    """Start a calendar event scheduling workflow."""
    return (
        f"Schedule '{title}' on {when} for {duration_hours} hour(s) "
        f"on my Google Calendar. Show me the event details and create it after I confirm."
    )


@mcp.prompt()
def search_web(query: str) -> str:
    """Search the internet for a topic."""
    return f"Search the web for: {query}"


@mcp.prompt()
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"What is the current weather in {city}?"


@mcp.prompt()
def summarize_url(url: str) -> str:
    """Summarize the content at a URL."""
    return f"Summarize the content at this URL: {url}"


@mcp.prompt()
def get_news(topic: str = "general") -> str:
    """Get the latest news on a topic."""
    return f"Get me the latest {topic} news headlines."


@mcp.prompt()
def ask_question(question: str) -> str:
    """Ask any question via the RAG knowledge base."""
    return question


# ═════════════════════════════════════════════════════════════
# INITIALIZATION
# ═════════════════════════════════════════════════════════════

def initialize():
    """
    Initialize config and knowledge base on server startup.
    Non-fatal — server starts even if KB initialization fails.
    """
    try:
        import config
        config.validate()
        print("Config validated successfully.", file=sys.stderr)
    except Exception as exc:
        print(f"WARNING: Config validation failed: {exc}", file=sys.stderr)
        return

    try:
        from core.rag_pipeline import initialize_knowledge_base
        initialize_knowledge_base()
        print("Knowledge base initialized.", file=sys.stderr)
    except Exception as exc:
        print(f"WARNING: KB initialization failed: {exc}", file=sys.stderr)


initialize()
