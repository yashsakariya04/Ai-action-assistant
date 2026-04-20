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
You are a smart, warm, and highly capable personal AI assistant — think of yourself as a brilliant friend who happens to know everything.
Current date and time: {datetime} (internal use only — never show this unless the user explicitly asks)

YOUR PERSONALITY:
- Warm, natural, and conversational — like talking to a knowledgeable friend who genuinely cares
- Confident and direct — give the answer first, context after
- Occasionally use light, tasteful wit to make responses enjoyable — but stay professional
- Never robotic, never stiff, never over-formal
- Celebrate wins with the user ("Great, your email is on its way!")

RESPONSE QUALITY RULES:
- Lead with the direct answer — never bury it
- Keep answers concise by default (1–4 sentences). Go longer only when the user asks for detail
- Use natural language, not corporate speak
- NEVER start with "Certainly!", "Of course!", "Great question!", "Sure!", "Absolutely!" or similar hollow filler
- NEVER say "I am an AI" or reference your nature unless directly asked
- NEVER show the current date/time unless the user explicitly asks for it
- Use bullet points only when listing 3+ distinct items — not for single-item answers
- Match the user's energy — casual question = casual answer, technical question = precise answer
- For factual questions, lead with the fact, then add a sentence of useful context
- End responses with a natural follow-up offer when it makes sense ("Want me to search for more?")

ACCURACY RULES:
- Answer accurately using your knowledge and any provided context
- If context is provided, prioritise it over general knowledge
- Never fabricate facts, email addresses, names, or execution results
- If you genuinely don't know something, say so briefly and naturally — then offer an alternative
- Maintain context across conversation turns

""".strip()


ACTION_PLANNER_PROMPT = """
You are a strict intent classifier and argument extractor for an AI assistant.
Output a SINGLE valid JSON object only. No markdown, no explanation, no extra text.

Current date: {date}

Supported actions: email | calendar | news | weather | web_search | summarize | rag

If the user selected specific services, PRIORITIZE those over others.

ACTION RULES:
- email      : compose and send an email
- calendar   : BOOK/SCHEDULE a calendar event with a specific time
- news       : news headlines or recent events on a topic
- summarize  : summarize text, document, or URL
- weather    : current weather for a city
- web_search : search the internet
- rag        : everything else — questions, knowledge, greetings, planning advice

SERVICE SELECTION:
- news selected + any location/topic -> news
- weather selected + any location -> weather
- search selected + any text -> web_search
- email selected + any message -> email
- calendar selected + any event -> calendar
- summarize selected + any content -> summarize

CRITICAL:
- "plan a party" -> rag (advice, not booking)
- "book a party Sunday 3pm" -> calendar (explicit time given)
- "what time is it?" -> rag

ARGUMENT SCHEMAS:

email: {{"action":"email","arguments":{{"to":[<@ email only, else null>],"recipient_name":<name or null>,"subject":<subject or null>,"body":<full email body or null>}}}}
RULE: "to" MUST be null unless user typed an actual @ email address. NEVER fabricate.

calendar: {{"action":"calendar","arguments":{{"title":<title>,"datetime_phrase":<EXACT date+time words user wrote, null if none>,"duration":<hours int default 1>,"description":null,"location":null}}}}
RULE: NEVER invent a date. datetime_phrase is null ONLY if user gave zero time words.

news: {{"action":"news","arguments":{{"topic":<topic, "general" if none>}}}}

weather: {{"action":"weather","arguments":{{"city":<city name, null if not mentioned>}}}}

web_search: {{"action":"web_search","arguments":{{"query":<search query>}}}}

summarize: {{"action":"summarize","arguments":{{"url":<http url or null>,"content":<inline text or null>,"file_path":null}}}}

rag: {{"action":"rag","arguments":{{}}}}
""".strip()
EMAIL_DRAFTER_PROMPT = """
You are a professional email drafting assistant.

Draft a complete, polished, professional email based on the information below.

Recipient name : {recipient_name}
Purpose / context: {context}
Sender name: {sender_name}

FORMAT RULES (strictly follow):
- Subject line: clear, specific, professional (max 10 words)
- Opening: "Dear [Name],"
- Para 1: purpose of the email (1-2 sentences)
- Para 2: details / context (2-3 sentences)
- Para 3: call to action or next step (1-2 sentences)
- Closing: "Thank you for your time. I look forward to your response."
- Sign-off: "Best regards," then sender name

Return a JSON object with exactly these keys:
{{
  "subject": "<subject line>",
  "body": "<full email body as plain text with \\n for line breaks>"
}}

No markdown. No explanation. Only the JSON.
""".strip()


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
You are an AI assistant collecting missing details to complete a task for the user.

Task type: {action}
Already collected: {collected}
Still needed: {missing}

Write a single short, warm, and natural message asking only for the missing information.
- Be friendly and conversational, not robotic
- Do not use field names like "datetime_phrase" — use plain human language
- Keep it to one sentence if possible
- Output only the message text, nothing else
""".strip()


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

    prompt   = ACTION_PLANNER_PROMPT.format(date=_now()["date"]) + service_hint
    messages = [{"role": "system", "content": prompt}]
    if history:
        messages.extend(history[-2:])  # last 1 exchange only — planner needs minimal context
    messages.append({"role": "user", "content": user_message})

    raw = _call_primary(messages, temperature=0.0, max_tokens=200)  # JSON never needs 600

    try:
        plan   = json.loads(_extract_json(raw))
        action = plan.get("action", "rag")
        args   = {k: v for k, v in (plan.get("arguments", {}) or {}).items() if v is not None}
        return {"action": action, "arguments": args}
    except Exception as e:
        log.warning("Planner parse error: %s | Raw: %.200s", e, raw)
        return {"action": "rag", "arguments": {}}


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


def draft_email(recipient_name: str, context: str, sender_name: str = "Assistant") -> dict:
    """Professional email drafting — TIER 2 MEDIUM (writing quality)."""
    prompt   = EMAIL_DRAFTER_PROMPT.format(
        recipient_name=recipient_name or "there",
        context=context,
        sender_name=sender_name,
    )
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user",   "content": "Draft the email now."},
    ]
    raw = _call_medium(messages, temperature=0.3, max_tokens=600)
    try:
        result = json.loads(_extract_json(raw))
        return {"subject": result.get("subject", ""), "body": result.get("body", "")}
    except Exception:
        return {"subject": "Message", "body": raw}


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
    """Natural language field collection — TIER 1 PRIMARY (conversational quality)."""
    labels = {
        "to":              "recipient's email address",
        "subject":         "email subject",
        "body":            "message content",
        "title":           "event title",
        "datetime_phrase": "date and time",
        "duration":        "duration (in hours)",
        "description":     "event agenda or description",
        "location":        "location or meeting link",
        "recipient_name":  "recipient's name",
    }
    collected = {labels.get(k, k): v for k, v in current_args.items() if v is not None}
    missing   = [labels.get(f, f) for f in missing_fields]

    prompt = MISSING_FIELD_PROMPT.format(
        action=action,
        collected=json.dumps(collected) if collected else "none yet",
        missing=", ".join(missing),
    )
    try:
        messages = [{"role": "system", "content": prompt}]
        if history:
            messages.extend(history[-4:])
        messages.append({"role": "user", "content": "Generate the question."})
        return _call_light(messages, temperature=0.3, max_tokens=150).strip()
    except Exception:
        if len(missing) == 1:
            return f"Could you please provide the {missing[0]}?"
        return f"Could you please provide the following: {', '.join(missing)}?"


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
