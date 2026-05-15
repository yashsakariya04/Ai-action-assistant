"""
llm_service.py — All LLM calls routed across 3 tiers.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLM TIER ROUTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  TIER 1 — PRIMARY   model: openai/gpt-oss-120b      key: GROQ_API_KEY_PRIMARY
    → plan_action()            intent detection + argument extraction
    → detect_confirmation()    yes / no / new_info classification
    → generate_missing_field_prompt()  natural language field collection
    → get_llm_response()       RAG answer synthesis

  TIER 2 — MEDIUM    model: llama-3.3-70b-versatile  key: GROQ_API_KEY_MEDIUM
    → draft_email()            professional email writing
    → draft_event_description() calendar event description
    → summarize via LLM        long-context document summarization

  TIER 3 — LIGHT     model: llama-3.1-8b-instant     key: GROQ_API_KEY_LIGHT
    → _call_light()            weather / news / search response formatting
                               general conversation fallback

  If a tier key is not configured it falls back to GROQ_API_KEY_PRIMARY
  automatically — so a single-key setup works with no changes.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import re
from datetime import datetime

import config
from groq import Groq

log = logging.getLogger(__name__)

# ── One Groq client per API key ───────────────────────────────
_clients: dict[str, Groq] = {}


def _get_client(api_key: str) -> Groq:
    """Return a cached Groq client for the given API key."""
    if api_key not in _clients:
        if not api_key:
            raise RuntimeError("Groq API key is not configured.")
        _clients[api_key] = Groq(api_key=api_key)
    return _clients[api_key]


def _now() -> dict:
    now = datetime.now()
    return {
        "date":     now.strftime("%A, %B %d %Y"),
        "time":     now.strftime("%I:%M %p"),
        "datetime": now.strftime("%A, %B %d %Y at %I:%M %p"),
        "iso":      now.isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# CORE CALL — routes to the correct tier
# ─────────────────────────────────────────────────────────────

def _call(
    messages: list,
    tier: str = "primary",       # "primary" | "medium" | "light"
    max_tokens: int = 800,
    temperature: float = 0.4,
) -> str:
    """
    Send messages to the appropriate tier's model + API key.

    tier="primary" → GROQ_API_KEY_PRIMARY + GROQ_MODEL_PRIMARY
    tier="medium"  → GROQ_API_KEY_MEDIUM  + GROQ_MODEL_MEDIUM
    tier="light"   → GROQ_API_KEY_LIGHT   + GROQ_MODEL_LIGHT

    On RateLimitError the tier automatically retries with the primary key
    as a last resort before returning a user-friendly message.
    """
    from groq import RateLimitError, APIStatusError

    tier_map = {
        "primary": (config.GROQ_API_KEY_PRIMARY, config.GROQ_MODEL_PRIMARY),
        "medium":  (config.GROQ_API_KEY_MEDIUM,  config.GROQ_MODEL_MEDIUM),
        "light":   (config.GROQ_API_KEY_LIGHT,   config.GROQ_MODEL_LIGHT),
    }
    api_key, model = tier_map.get(tier, tier_map["primary"])

    # Build attempt list: requested tier first, then primary as fallback
    # (avoids duplicate if they share the same key)
    attempts = [(api_key, model)]
    if tier != "primary" and api_key != config.GROQ_API_KEY_PRIMARY:
        attempts.append((config.GROQ_API_KEY_PRIMARY, config.GROQ_MODEL_PRIMARY))

    last_err = ""
    for key, mdl in attempts:
        try:
            client   = _get_client(key)
            response = client.chat.completions.create(
                model=mdl,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if mdl != model:
                log.info("LLM tier fallback: used %s instead of %s", mdl, model)
            return response.choices[0].message.content.strip()

        except RateLimitError as exc:
            last_err = str(exc)
            log.warning("Rate limit on model '%s': %s", mdl, last_err[:120])
            continue

        except APIStatusError as exc:
            log.error("Groq API error %s on model '%s': %s", exc.status_code, mdl, str(exc)[:200])
            return f"The AI service returned an error ({exc.status_code}). Please try again."

    # All attempts exhausted
    m = re.search(r"try again in ([\w.]+)", last_err)
    retry = f" Resets in {m.group(1)}." if m else ""
    log.error("All LLM attempts rate-limited. Last: %s", last_err[:200])
    return (
        f"The AI model has hit its token limit for today.{retry} "
        f"Weather, news, search, email, and calendar still work normally. "
        f"Try again shortly or add GROQ_API_KEY_MEDIUM / GROQ_API_KEY_LIGHT in .env."
    )


# Convenience aliases used internally
def _call_primary(messages, max_tokens=800, temperature=0.4):
    return _call(messages, tier="primary", max_tokens=max_tokens, temperature=temperature)

def _call_medium(messages, max_tokens=800, temperature=0.4):
    return _call(messages, tier="medium", max_tokens=max_tokens, temperature=temperature)

def _call_light(messages, max_tokens=800, temperature=0.4):
    return _call(messages, tier="light", max_tokens=max_tokens, temperature=temperature)

# Legacy alias — keeps any external callers working
def _call_groq(messages, max_tokens=800, temperature=0.4):
    return _call_primary(messages, max_tokens=max_tokens, temperature=temperature)


# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPTS
# ─────────────────────────────────────────────────────────────

BASE_SYSTEM_PROMPT = """
You are AI Action Assistant — a professional AI productivity assistant built for real-world task execution.
Current date and time: {datetime} (internal use only — never show this unless the user explicitly asks)

You are precise, concise, and helpful. You do NOT engage in casual small talk.
Respond in 1-3 sentences maximum unless detail is required.
Never say "Great question!", "Certainly!", "Of course!", "Sure!", "Absolutely!" or any filler phrases.
Never say "I am an AI" or reference your nature unless directly asked.
Never show the current date/time unless the user explicitly asks.
Lead with the direct answer — never bury it.
For factual questions, lead with the fact, then add one sentence of useful context.
If context is provided, prioritise it over general knowledge.
Never fabricate facts, email addresses, names, or execution results.
If you don't know something, say so briefly and offer to search the web.
When asked what you can do, list your actual capabilities: send emails via Gmail, schedule Google Calendar events, fetch live weather, get news headlines, search the web, and summarize uploaded documents (PDF/DOCX/XLSX/TXT).
""".strip()


INTENT_CLASSIFIER_PROMPT = """
You are a strict intent classifier for an AI assistant. Your only job is to output a
JSON object identifying the user's intent. Output ONLY valid JSON. No prose. No markdown.
No explanation. No code fences.

INTENT TYPES (use EXACTLY these strings):
- "email"      : user wants to send an email or compose a message
- "calendar"   : user wants to schedule, create, or set a reminder/event/meeting
- "weather"    : user wants weather or temperature info for any location
- "news"       : user wants news headlines or recent articles on a topic
- "web_search" : user asks about a person, fact, entity, definition, or current event
- "summarize"  : user wants a document or file summarized
- "rag"        : user asks something from the assistant's knowledge base
- "cancel"     : user wants to cancel the current action
- "greeting"   : user is saying hello or greeting

STRICT ROUTING RULES:
1. "who is X", "what is X", "tell me about X" → ALWAYS "web_search"
2. Any message with send/mail/email keyword → ALWAYS "email"
3. Any message with schedule/meeting/reminder/event keyword → ALWAYS "calendar"
4. Greetings (hi/hello/hey) → ALWAYS "greeting"
5. Cancel words alone → ALWAYS "cancel"
6. Weather/temperature queries → ALWAYS "weather"
7. News/headlines queries → ALWAYS "news"
8. Only use "rag" if NO other rule matches

OUTPUT FORMAT (strict):
{{
  "action": "<intent_type>",
  "confidence": <0.0 to 1.0>,
  "extracted": {{
    "to": "<email address if mentioned, else null>",
    "subject": "<subject if mentioned, else null>",
    "body_hint": "<any body content hint if mentioned, else null>",
    "title": "<event title if mentioned, else null>",
    "date": "<date expression if mentioned, else null>",
    "time": "<time expression if mentioned, else null>",
    "location": "<city/location if mentioned, else null>",
    "query": "<search query or news topic if mentioned, else null>"
  }}
}}

User message: {user_message}
Conversation context (last 3 turns): {conversation_context}
""".strip()

# Legacy alias
ACTION_PLANNER_PROMPT = INTENT_CLASSIFIER_PROMPT
EMAIL_BODY_GENERATION_PROMPT = """
You are writing a professional email body. Write ONLY the email body content.
No subject line. No "To:" or "From:" headers. No sign-off unless natural.
Be concise, professional, and appropriate for the context provided.
Subject: {subject}
Recipient: {recipient}
Context/Hint: {hint}
Write the email body now:
""".strip()

EMAIL_DRAFTER_PROMPT = EMAIL_BODY_GENERATION_PROMPT


CALENDAR_DESCRIPTION_PROMPT = """
You are helping create a professional Google Calendar event description.

Event title: {title}
Context provided by user: {context}

Write a structured event description with these sections (plain text, use dashes for bullets):
- Preparation Required

Keep it concise and professional. No emojis.
Return only the description text, no JSON.
""".strip()


MISSING_FIELD_PROMPT = """
You are an AI assistant collecting missing details to complete a task.

Task type: {action}
Already collected: {collected}
Still needed: {missing}

Write ONE short, direct sentence asking only for the FIRST missing item.
- Do not use field names like "datetime_phrase" — use plain human language
- Do not repeat a question already asked in the conversation
- Do not ask for multiple fields at once
- Output only the question text, nothing else
""".strip()


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

AUTO_GENERATE_SIGNALS = frozenset([
    "auto", "generate", "write it", "write it yourself", "make it", "create it",
    "at your own", "yourself", "auto generate", "auto-generate", "make content",
    "birthday wishes", "professional", "formal", "casual", "short", "brief",
    "use that", "from weather", "from the weather", "weather data", "get it from",
    "use previous", "use above", "use last result", "from news", "use news",
    "you write", "you decide", "just write", "write something", "draft it",
    "make a content",
])

# FIXED: E-3 — signals that mean "use the last weather/news/search result as email body"
LAST_RESULT_SIGNALS = frozenset([
    "get it from weather", "use weather data", "use the weather", "from weather api",
    "from the weather", "use previous result", "use that data", "use above data",
    "use that", "use it", "from previous", "from above", "use last result",
    "get from news", "use news data", "use the news", "from news",
    "use search result", "from search", "use web result",
])

# FIXED: C-3 — strong new-intent keywords that should clear stale pending state
STRONG_INTENT_KEYWORDS = frozenset([
    "send", "email", "mail", "schedule", "remind", "reminder", "meeting",
    "weather", "news", "search", "summarize", "summarise", "book", "create event",
    "add to calendar", "set up", "compose", "forward",
])

# Signals that cancel any pending action
CANCEL_SIGNALS = frozenset([
    "exit", "cancel", "stop", "quit", "nevermind", "never mind",
    "forget it", "abort", "nope", "no thanks", "drop it", "skip it",
])

# Capability query patterns
CAPABILITY_PATTERNS = frozenset([
    "what can you do", "what are your features", "help", "capabilities",
    "what do you support", "what can you help", "what do you do",
    "show me what you can do", "list your features",
])

# ─────────────────────────────────────────────────────────────
# PUBLIC FUNCTIONS — each uses its assigned tier
# ─────────────────────────────────────────────────────────────

def get_llm_response(query: str, context: str = "", history: list = None) -> str:
    """RAG answer synthesis — TIER 1 PRIMARY (best quality answers)."""
    now    = _now()
    system = BASE_SYSTEM_PROMPT.format(datetime=now["datetime"])
    if context:
        system += "\n\nCONTEXT (use this to answer):\n" + context

    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-6:])  # 3 exchanges is enough context
    messages.append({"role": "user", "content": query})

    return _call_primary(messages, temperature=0.6, max_tokens=800)


def _format_conversation_context(history: list | None) -> str:
    if not history:
        return "(none)"
    lines = []
    for turn in history[-6:]:
        role = turn.get("role", "user").upper()
        lines.append(f"{role}: {turn.get('content', '')}")
    return "\n".join(lines) if lines else "(none)"


def _extracted_to_arguments(action: str, extracted: dict) -> dict:
    """Map classifier extracted fields to action arguments."""
    extracted = extracted or {}
    args = {}
    if action == "email":
        to = extracted.get("to")
        if to:
            args["to"] = [to] if isinstance(to, str) else to
        if extracted.get("subject"):
            args["subject"] = extracted["subject"]
        if extracted.get("body_hint"):
            args["body"] = extracted["body_hint"]
    elif action == "calendar":
        if extracted.get("title"):
            args["title"] = extracted["title"]
        date_p = extracted.get("date") or ""
        time_p = extracted.get("time") or ""
        if date_p or time_p:
            args["datetime_phrase"] = f"{date_p} {time_p}".strip()
    elif action == "weather":
        if extracted.get("location"):
            args["city"] = extracted["location"]
    elif action == "news":
        args["topic"] = extracted.get("query") or "general"
    elif action == "web_search":
        args["query"] = extracted.get("query") or ""
    return {k: v for k, v in args.items() if v is not None}


def plan_action(user_message: str, history: list = None, selected_services: list = None) -> dict:
    """Intent detection + argument extraction — TIER 1 PRIMARY (critical accuracy)."""
    selected_services = selected_services or []

    service_hint = ""
    if selected_services:
        mapping = {
            "weather": "weather", "news": "news", "search": "web_search",
            "email": "email", "calendar": "calendar", "summarize": "summarize",
        }
        mapped = [mapping.get(s, s) for s in selected_services if s in mapping]
        if mapped:
            service_hint = (
                f"\n\nUSER SELECTED SERVICES: {', '.join(mapped)}\n"
                f"If the user message could match any of these services, strongly prefer them over 'rag'."
            )

    prompt = INTENT_CLASSIFIER_PROMPT.format(
        user_message=user_message,
        conversation_context=_format_conversation_context(history),
    ) + service_hint
    messages = [{"role": "system", "content": prompt}]
    messages.append({"role": "user", "content": user_message})

    raw = _call_primary(messages, temperature=0.0, max_tokens=250)

    try:
        plan = json.loads(_extract_json(raw))
        action = plan.get("action", "rag")
        extracted = plan.get("extracted", {}) or {}
        args = _extracted_to_arguments(action, extracted)
        legacy = plan.get("arguments", {}) or {}
        for k, v in legacy.items():
            if v is not None:
                args[k] = v
        return {"action": action, "arguments": args, "confidence": plan.get("confidence", 0.5)}
    except Exception as e:
        log.warning("Planner parse error: %s | Raw: %.200s", e, raw)
        return {"action": "rag", "arguments": {}}


def classify_intent_with_llm(user_message: str, history: list = None, selected_services: list = None) -> str:
    """Return intent action string from LLM classifier."""
    plan = plan_action(user_message, history=history, selected_services=selected_services)
    return plan.get("action", "rag")


def detect_confirmation(user_message: str, pending_action: str) -> str:
    """Confirm / cancel / new_info classification — TIER 1 PRIMARY (nuance needed)."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are classifying a user reply in a conversation where the assistant "
                f"just previewed a pending '{pending_action}' action and asked for confirmation.\n\n"
                "Classify the user reply into exactly one of:\n"
                "  confirm  — user agrees / wants to proceed\n"
                "  cancel   — user wants to abort / stop\n"
                "  new_info — user is providing corrections or new details\n\n"
                "Output exactly one word: confirm | cancel | new_info\n"
                "No punctuation. No explanation."
            ),
        },
        {"role": "user", "content": user_message},
    ]
    try:
        result = _call_light(messages, temperature=0.0, max_tokens=10).strip().lower()
        if result in ("confirm", "cancel", "new_info"):
            return result
        if any(w in result for w in ("confirm", "yes", "ok", "sure")):
            return "confirm"
        if any(w in result for w in ("cancel", "no", "abort", "stop")):
            return "cancel"
        return "new_info"
    except Exception:
        return "new_info"


def generate_email_body(subject: str, recipient: str, hint: str) -> str:
    """Auto-generate email body — TIER 2 MEDIUM."""
    prompt = EMAIL_BODY_GENERATION_PROMPT.format(
        subject=subject or "Message",
        recipient=recipient or "there",
        hint=hint or "",
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Write the email body now."},
    ]
    return _call_medium(messages, temperature=0.3, max_tokens=600).strip()


def draft_email(recipient_name: str, context: str, sender_name: str = "Assistant") -> dict:
    """Professional email drafting — TIER 2 MEDIUM (writing quality)."""
    body = generate_email_body(
        subject="Message",
        recipient=recipient_name or "there",
        hint=context,
    )
    return {"subject": "Message", "body": body}


def draft_event_description(title: str, context: str) -> str:
    """Calendar event description — TIER 2 MEDIUM (structured writing)."""
    prompt   = CALENDAR_DESCRIPTION_PROMPT.format(title=title, context=context or title)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user",   "content": "Generate the description."},
    ]
    try:
        return _call_medium(messages, temperature=0.3, max_tokens=400).strip()
    except Exception:
        return ""


def generate_missing_field_prompt(
    action: str,
    missing_fields: list,
    current_args: dict,
    history: list = None,
) -> str:
    # FIXED: A-4 (response format) — deterministic spec-format prompts, no LLM free-form text
    first = missing_fields[0] if missing_fields else ""

    if action == "email":
        questions = {
            "to":      "Who should I send this email to? Please provide the email address.",
            "subject": "What should be the subject of this email?",
            "body":    "What should the email say? (or say 'auto-generate' and I'll write it for you)",
        }
        question = questions.get(first, f"Please provide the {first}.")
        return f"\u25cb PENDING \u00b7 EMAIL\n{question}\n\u2192 Type your reply to continue"

    if action == "calendar":
        questions = {
            "title":           "What is the title or purpose of this event?",
            "datetime_phrase": "What date should I schedule this for? (e.g., tomorrow, next Friday, May 20)",
            "time":            "What time should this be scheduled for? (e.g., 3 PM, 10:30 AM)",
        }
        question = questions.get(first, f"Please provide the {first}.")
        return f"\u25cb PENDING \u00b7 CALENDAR\n{question}\n\u2192 Type your reply to continue"

    # Fallback for other action types
    labels = {
        "to":              "recipient's email address",
        "subject":         "email subject",
        "body":            "message content",
        "title":           "event title",
        "datetime_phrase": "date and time",
        "duration":        "duration (in hours)",
        "city":            "city name",
        "query":           "search query",
    }
    label = labels.get(first, first)
    return f"Could you please provide the {label}?"


# ─────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    if not raw.startswith("{"):
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return m.group(0)
    return raw
