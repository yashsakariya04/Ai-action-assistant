"""
chat_engine.py — Core logic: processes one message and returns a structured response.

7-step pipeline:
  0. Pre-classify intent (regex) + stale-state override
  1. Confirmation gate (yes/no only when awaiting)
  2. Classify intent (regex or LLM)
  3. Route to handler (email/calendar/weather/news/search/rag/summarize/greeting/cancel)
  4. Validate (anti-hallucination via action_controller)
  5. Collect missing fields (multi-turn email/calendar)
  6. Preview + await confirmation (email/calendar only)
  7. Execute confirmed action (real API calls only)
"""

import logging
import re
import time
from datetime import datetime, timedelta, date

import config

log = logging.getLogger(__name__)

from core.llm_service import (
    plan_action,
    classify_intent_with_llm,
    generate_email_body,
    detect_confirmation,
    draft_event_description,
    AUTO_GENERATE_SIGNALS,
    CANCEL_SIGNALS,
    LAST_RESULT_SIGNALS,
    CAPABILITY_PATTERNS,
)
from core.action_controller import validate_action
from core.validators import extract_emails_from_text, is_valid_email_format
from services.news_service import fetch_raw_news
from services.weather_service import fetch_weather
from services.web_search_service import search_web
from services.email_service import send_email
from services.calendar_service import create_calendar_event
from core.intent_parser import extract_datetime
from core.rag_pipeline import run_rag
from backend.session_store import Session, get_default_flow_state
from backend.schemas import ChatResponse, NewsArticle
from services.summarizer_service import summarize

# ── Fixed responses (no LLM) ─────────────────────────────────
_GREETING_RESPONSE = (
    "Hello! I'm AI Action Assistant. I can help you:\n"
    "• Send emails via Gmail\n"
    "• Schedule Google Calendar events\n"
    "• Check live weather for any city\n"
    "• Fetch the latest news on any topic\n"
    "• Search the web for any information\n"
    "• Summarize uploaded documents (PDF, DOCX, XLSX, TXT)\n\n"
    "What would you like to do?"
)

_CAPABILITY_RESPONSE = (
    "I can send emails via Gmail, schedule Google Calendar events, check live weather, "
    "fetch news headlines, search the web, and summarize uploaded documents "
    "(PDF, DOCX, XLSX, TXT)."
)


def _r(status: str, action: str, message: str, **kwargs) -> ChatResponse:
    return ChatResponse(status=status, action=action, message=message, **kwargs)


def _require_real_execution(action_type: str, result: dict) -> None:
    if result.get("status") == "success" and not result.get("_execution_attempted", False):
        raise RuntimeError(
            f"[A-4] {action_type} returned success without a real API call. "
            "Blocking hallucinated success response."
        )


def _get_user_messages(memory) -> list:
    return [
        m["content"]
        for m in memory.get_buffer()
        if m.get("role") == "user" and m.get("content")
    ]


def _remember_turn(memory, user_msg: str, assistant_msg: str) -> None:
    memory.add("user", user_msg)
    memory.add("assistant", assistant_msg)


# ═══════════════════════════════════════════════════════════════
# CHANGE 1 — Pre-Classifier Regex Layer
# ═══════════════════════════════════════════════════════════════

def pre_classify_intent(message: str) -> str | None:
    # FIXED: BUG-I1, BUG-I2, BUG-I3 — deterministic regex intent pre-classifier
    msg = message.lower().strip()

    CANCEL_ONLY = r'^(cancel|stop|exit|quit|nevermind|no thanks|abort|nope|forget it)[\.\!]?$'
    if re.match(CANCEL_ONLY, msg):
        return "cancel"

    EMAIL_KW = r'\b(send|email|mail|forward|compose|write a mail|shoot a mail|draft a mail)\b'
    if re.search(EMAIL_KW, msg):
        return "email"

    CALENDAR_KW = r'\b(schedule|remind|reminder|meeting|event|appointment|book|add to calendar|create event|set up a|plan a)\b'
    if re.search(CALENDAR_KW, msg):
        return "calendar"

    WEATHER_KW = r'\b(weather|temperature|temp|humidity|forecast|rainfall|sunny|raining|climate)\b'
    if re.search(WEATHER_KW, msg):
        return "weather"

    NEWS_KW = r'\b(news|headlines|latest news|breaking news|today.?s news|top stories)\b'
    if re.search(NEWS_KW, msg):
        return "news"

    SEARCH_KW = r'\b(who is|what is|tell me about|search for|look up|find info|latest on|when did|where is)\b'
    if re.search(SEARCH_KW, msg):
        return "web_search"

    GREET_KW = r'^(hey|hi|hello|good morning|good evening|good afternoon|sup|yo|hiya|howdy)[\!\.\,]?$'
    if re.match(GREET_KW, msg):
        return "greeting"

    return None


# ═══════════════════════════════════════════════════════════════
# CHANGE 11 — Clear pending state
# ═══════════════════════════════════════════════════════════════

def clear_pending_state(session: Session) -> None:
    # FIXED: BUG-I4, BUG-I5, BUG-E4 — atomically clear all pending action state
    session.awaiting_confirmation = False
    session.flow = get_default_flow_state()
    session.memory.clear_pending_action()


# ═══════════════════════════════════════════════════════════════
# CHANGE 9 — Natural language date/time parser
# ═══════════════════════════════════════════════════════════════

def next_weekday(from_date: date, weekday: int) -> date:
    days_ahead = weekday - from_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return from_date + timedelta(days=days_ahead)


def parse_natural_date(text: str) -> date | None:
    # FIXED: BUG-C3 — parse natural language dates
    t = text.lower().strip()
    today = datetime.now().date()

    if "today" in t:
        return today
    if "tomorrow" in t:
        return today + timedelta(days=1)
    if "day after" in t:
        return today + timedelta(days=2)
    if "next monday" in t:
        return next_weekday(today, 0)
    if "next tuesday" in t:
        return next_weekday(today, 1)
    if "next wednesday" in t:
        return next_weekday(today, 2)
    if "next thursday" in t:
        return next_weekday(today, 3)
    if "next friday" in t:
        return next_weekday(today, 4)
    if "next saturday" in t:
        return next_weekday(today, 5)
    if "next sunday" in t:
        return next_weekday(today, 6)
    if "next week" in t:
        return today + timedelta(weeks=1)

    try:
        from dateutil import parser as dateutil_parser
        parsed = dateutil_parser.parse(text, fuzzy=True, default=datetime.now())
        if parsed.date() >= today:
            return parsed.date()
    except Exception:
        pass

    return None


def parse_natural_time(text: str) -> str | None:
    # FIXED: BUG-C3 — parse natural language times
    t = text.lower().strip()

    match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', t)
    if match:
        h, m = int(match.group(1)), int(match.group(2))
        meridiem = match.group(3)
        if meridiem == "pm" and h != 12:
            h += 12
        if meridiem == "am" and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"

    match = re.search(r'(\d{1,2})\s*(am|pm)', t)
    if match:
        h = int(match.group(1))
        meridiem = match.group(2)
        if meridiem == "pm" and h != 12:
            h += 12
        if meridiem == "am" and h == 12:
            h = 0
        return f"{h:02d}:00"

    if "morning" in t:
        return "09:00"
    if "afternoon" in t:
        return "14:00"
    if "evening" in t:
        return "18:00"
    if "night" in t:
        return "20:00"
    if "noon" in t:
        return "12:00"
    if "midnight" in t:
        return "00:00"

    return None


def extract_duration(text: str) -> int | None:
    t = text.lower()
    match = re.search(r'(\d+)\s*(hour|hr|h)\b', t)
    if match:
        return int(match.group(1)) * 60
    match = re.search(r'(\d+)\s*(minute|min|m)\b', t)
    if match:
        return int(match.group(1))
    return None


def combine_date_time(date_val, time_val: str) -> datetime:
    if isinstance(date_val, str):
        date_val = datetime.fromisoformat(date_val).date()
    h, m = map(int, time_val.split(":"))
    return datetime.combine(date_val, datetime.min.time().replace(hour=h, minute=m))


# ═══════════════════════════════════════════════════════════════
# Field extraction helpers
# ═══════════════════════════════════════════════════════════════

def extract_email_address(text: str) -> str | None:
    emails = extract_emails_from_text(text)
    return emails[0] if emails else None


def validate_email_address(addr: str) -> bool:
    return is_valid_email_format(addr)


def extract_event_title(text: str) -> str | None:
    t = text.strip()
    lower = t.lower()

    if "reminder" in lower and "schedule" not in lower[:20]:
        m = re.search(r'reminder\s+(?:for\s+)?(.+?)(?:\s+(?:on|at|next|tomorrow)|$)', lower)
        if m:
            cand = re.sub(
                r'\b(next\s+\w+|tomorrow|today|\d{1,2}\s*(?:am|pm|:))\b.*',
                '', m.group(1), flags=re.I,
            ).strip()
            if len(cand) >= 3:
                return cand.title()

    for pat in [
        r'\b(?:schedule|set|create|book|plan)\s+(?:a\s+)?(?:meeting|event|appointment)\s+(?:about\s+|for\s+)?(.+?)(?:\s+(?:on|at|for next|tomorrow)|$)',
        r'\b(?:schedule|book)\s+(?:a\s+)?(.+?)(?:\s+(?:on|at|for|tomorrow|next)|$)',
    ]:
        m = re.search(pat, lower)
        if m:
            cand = re.sub(
                r'\b(next\s+\w+|tomorrow|today|\d{1,2}\s*(?:am|pm|:))\b.*',
                '', m.group(1), flags=re.I,
            ).strip()
            if len(cand) >= 3 and cand not in ("something", "it", "this", "reminder"):
                return cand.title()

    if re.search(r'\b(reminder|meeting|appointment|event)\b', lower):
        for kw, title in [("reminder", "Reminder"), ("meeting", "Meeting"), ("appointment", "Appointment")]:
            if kw in lower:
                return title
    return None


def extract_fields_from_message(user_message: str, action_type: str) -> dict:
    extracted = {}
    if action_type == "email":
        email = extract_email_address(user_message)
        if email:
            extracted["to"] = email
        m = re.search(
            r'\b(?:about|regarding|re:|subject:?)\s+(.+?)(?:\s+to\s+[\w.@]+|\s*$)',
            user_message, re.I,
        )
        if m:
            subj = m.group(1).strip().rstrip(".")
            if len(subj) > 2 and not extract_email_address(subj):
                extracted["subject"] = subj
    elif action_type == "calendar":
        title = extract_event_title(user_message)
        if title:
            extracted["title"] = title
        d = parse_natural_date(user_message)
        if d:
            extracted["date"] = d.isoformat()
        tm = parse_natural_time(user_message)
        if tm:
            extracted["time"] = tm
    return extracted


def extract_location(message: str) -> str:
    m = re.search(r'(?:weather|temperature|forecast)\s+(?:in|at|for)\s+([a-zA-Z\s,]+)', message, re.I)
    if m:
        return m.group(1).strip().rstrip("?.")
    m = re.search(r'(?:in|at|for)\s+([a-zA-Z\s,]{2,40})(?:\?|$)', message, re.I)
    return m.group(1).strip() if m else ""


def extract_topic(message: str) -> str:
    m = re.search(r'(?:news|headlines)\s+(?:on|about)\s+(.+)', message, re.I)
    return m.group(1).strip().rstrip("?.") if m else "general"


# ═══════════════════════════════════════════════════════════════
# CHANGE 5 — Unified missing field collector signals
# ═══════════════════════════════════════════════════════════════

def detect_auto_generate(text: str) -> bool:
    # FIXED: BUG-E3 — detect auto-generate intent
    t = text.lower().strip()
    return any(signal in t for signal in AUTO_GENERATE_SIGNALS)


def detect_cancel_signal(text: str) -> bool:
    # FIXED: BUG-E4, BUG-I5 — cancel during field collection
    t = text.lower().strip()
    return any(signal in t for signal in CANCEL_SIGNALS)


def detect_use_last_result(text: str) -> bool:
    # FIXED: BUG-E2 — use last weather/news/search as email body
    t = text.lower().strip()
    return any(signal in t for signal in LAST_RESULT_SIGNALS)


def _detect_confirmation_response(message: str) -> str | None:
    t = message.lower().strip()
    if re.match(r'^(yes|y|yeah|yep|confirm|ok|okay|sure|go ahead|do it|send it|create it)[\.\!]?$', t):
        return "yes"
    if re.match(r'^(no|n|nope|cancel|stop|abort|don\'?t|dont)[\.\!]?$', t):
        return "no"
    return None


def _is_capability_query(message: str) -> bool:
    lower = message.strip().lower()
    return any(pat in lower for pat in CAPABILITY_PATTERNS)


def handle_greeting() -> ChatResponse:
    # FIXED: BUG-R1 — hardcoded professional greeting, no LLM
    return _r("success", "greeting", _GREETING_RESPONSE)


# ═══════════════════════════════════════════════════════════════
# CHANGE 5 — collect_missing_fields
# ═══════════════════════════════════════════════════════════════

def collect_missing_fields(
    action_type: str,
    user_message: str,
    session: Session,
) -> tuple[str, object]:
    # FIXED: BUG-E2, BUG-E3, BUG-E4, BUG-C1 — unified field collector

    if detect_cancel_signal(user_message):
        clear_pending_state(session)
        return ("cancel", None)

    flow = session.flow
    collected = dict(flow.get("collected_fields", {}))

    extracted = extract_fields_from_message(user_message, action_type)
    for key, value in extracted.items():
        if value and key not in collected:
            collected[key] = value

    if action_type == "email":
        if "to" not in collected:
            email_in_msg = extract_email_address(user_message)
            if email_in_msg:
                collected["to"] = email_in_msg
            else:
                return ("ask", (
                    "\u25cb PENDING \u00b7 EMAIL\n"
                    "Who should I send this email to? Please provide the email address.\n"
                    "\u2192 Type your reply to continue"
                ))

        if "subject" not in collected:
            subj_from_msg = extracted.get("subject")
            if subj_from_msg and not detect_auto_generate(user_message):
                collected["subject"] = subj_from_msg
            elif (
                len(user_message.strip()) > 3
                and not detect_auto_generate(user_message)
                and not detect_use_last_result(user_message)
                and "@" not in user_message
                and not re.search(r'\b(send|mail|email)\b', user_message.lower())
            ):
                collected["subject"] = user_message.strip()
            else:
                return ("ask", (
                    "\u25cb PENDING \u00b7 EMAIL\n"
                    "What should be the subject of this email?\n"
                    "\u2192 Type your reply to continue"
                ))

        if "body" not in collected:
            last = session.last_result or {}
            if detect_use_last_result(user_message) and last.get("data"):
                body = f"Here is the latest {last.get('type', 'info')} update:\n\n{last['data']}"
                collected["body"] = body
            elif detect_auto_generate(user_message):
                subject = collected.get("subject", "")
                to_addr = collected.get("to", "")
                collected["body"] = generate_email_body(
                    subject=subject, recipient=to_addr, hint=user_message,
                )
            elif len(user_message.strip()) > 10 and not re.search(
                r'\b(send|mail|email|subject)\b', user_message.lower()
            ):
                collected["body"] = user_message.strip()
            else:
                return ("ask", (
                    "\u25cb PENDING \u00b7 EMAIL\n"
                    "What should the email say?\n"
                    "(Tip: say 'auto-generate' and I'll write it for you, "
                    "or 'use weather data' to include weather info)\n"
                    "\u2192 Type your reply to continue"
                ))

        flow["collected_fields"] = collected
        session.flow = flow
        return ("ready", collected)

    if action_type == "calendar":
        if "title" not in collected:
            title = extract_event_title(user_message)
            if title:
                collected["title"] = title
            else:
                return ("ask", (
                    "\u25cb PENDING \u00b7 CALENDAR\n"
                    "What is the title or purpose of this event?\n"
                    "\u2192 Type your reply to continue"
                ))

        if "date" not in collected:
            parsed_date = parse_natural_date(user_message)
            if parsed_date:
                collected["date"] = parsed_date.isoformat()
            else:
                return ("ask", (
                    "\u25cb PENDING \u00b7 CALENDAR\n"
                    "What date should I schedule this for?\n"
                    "(e.g., tomorrow, next Friday, May 20)\n"
                    "\u2192 Type your reply to continue"
                ))

        if "time" not in collected:
            parsed_time = parse_natural_time(user_message)
            if parsed_time:
                collected["time"] = parsed_time
            else:
                return ("ask", (
                    "\u25cb PENDING \u00b7 CALENDAR\n"
                    "What time should this be scheduled for?\n"
                    "(e.g., 3 PM, 10:30 AM, 9 in the morning)\n"
                    "\u2192 Type your reply to continue"
                ))

        if "duration" not in collected:
            collected["duration"] = extract_duration(user_message) or 60

        flow["collected_fields"] = collected
        session.flow = flow
        return ("ready", collected)

    return ("cancel", None)


# ═══════════════════════════════════════════════════════════════
# CHANGE 6 — Email flow handler
# ═══════════════════════════════════════════════════════════════

def handle_email_flow(
    user_message: str, session: Session,
) -> ChatResponse:
    # FIXED: BUG-E1, BUG-I1 — email must collect fields then preview before send
    flow = session.flow

    if flow.get("pending_action") != "email":
        flow["pending_action"] = "email"
        flow["collected_fields"] = {}
        flow["pending_fields"] = {"to": True, "subject": True, "body": True}
        flow["awaiting_confirmation"] = False
        flow["state_version"] = flow.get("state_version", 0) + 1
        session.awaiting_confirmation = False

        extracted = extract_fields_from_message(user_message, "email")
        for key, value in extracted.items():
            if value:
                flow["collected_fields"][key] = value
        email_addr = extract_email_address(user_message)
        if email_addr:
            flow["collected_fields"]["to"] = email_addr
        session.flow = flow

    status, result = collect_missing_fields("email", user_message, session)

    if status == "cancel":
        return _r("cancelled", "none", "Action cancelled.")

    if status == "ask":
        _remember_turn(session.memory, user_message, result)
        return _r("pending", "email", result)

    if status == "ready":
        fields = result
        if not validate_email_address(fields["to"]):
            session.flow["collected_fields"].pop("to", None)
            msg = (
                "\u25cb PENDING \u00b7 EMAIL\n"
                "That doesn't look like a valid email address. Please provide a valid email.\n"
                "\u2192 Type your reply to continue"
            )
            _remember_turn(session.memory, user_message, msg)
            return _r("pending", "email", msg)

        sep = "\u2500" * 44
        preview = (
            f"\u25cb AWAITING \u00b7 EMAIL\n"
            f"Email ready to send \u2014 please review:\n\n"
            f"To      : {fields['to']}\n"
            f"Subject : {fields['subject']}\n"
            f"{sep}\n"
            f"{fields['body']}\n"
            f"{sep}\n\n"
            f"Confirm sending? (yes / no)\n"
            f"\u2713 Confirm   \u2715 Cancel"
        )
        session.awaiting_confirmation = True
        flow["awaiting_confirmation"] = True
        flow["confirmation_payload"] = dict(fields)
        session.flow = flow
        memory_plan = {
            "action": "email",
            "arguments": {
                "to": [fields["to"]],
                "subject": fields["subject"],
                "body": fields["body"],
            },
            "missing_fields": [],
        }
        session.memory.set_pending_action(memory_plan)
        _remember_turn(session.memory, user_message, preview)
        return _r("awaiting", "email", preview,
                  preview={"to": [fields["to"]], "subject": fields["subject"], "body": fields["body"]})

    return _r("error", "email", "Unexpected email flow state.")


# ═══════════════════════════════════════════════════════════════
# CHANGE 7 — Calendar flow handler
# ═══════════════════════════════════════════════════════════════

def handle_calendar_flow(
    user_message: str, session: Session,
) -> ChatResponse:
    # FIXED: BUG-C1, BUG-C2, BUG-I2 — calendar field collection + preview
    flow = session.flow

    if flow.get("pending_action") != "calendar":
        flow["pending_action"] = "calendar"
        flow["collected_fields"] = {}
        flow["pending_fields"] = {"title": True, "date": True, "time": True}
        flow["awaiting_confirmation"] = False
        flow["state_version"] = flow.get("state_version", 0) + 1
        session.awaiting_confirmation = False

        extracted_title = extract_event_title(user_message)
        extracted_date = parse_natural_date(user_message)
        extracted_time = parse_natural_time(user_message)
        if extracted_title:
            flow["collected_fields"]["title"] = extracted_title
        if extracted_date:
            flow["collected_fields"]["date"] = extracted_date.isoformat()
        if extracted_time:
            flow["collected_fields"]["time"] = extracted_time
        session.flow = flow

    status, result = collect_missing_fields("calendar", user_message, session)

    if status == "cancel":
        return _r("cancelled", "none", "Action cancelled.")

    if status == "ask":
        _remember_turn(session.memory, user_message, result)
        return _r("pending", "calendar", result)

    if status == "ready":
        fields = result
        date_val = fields["date"]
        if isinstance(date_val, str):
            date_val = datetime.fromisoformat(date_val).date()
        event_dt = combine_date_time(date_val, fields["time"])
        duration = fields.get("duration", 60)
        dur_label = (
            f"{duration} minutes" if duration < 60
            else f"{duration // 60} hour{'s' if duration > 60 else ''}"
        )
        display_dt = event_dt.strftime("%A, %d %B %Y") + " at " + event_dt.strftime("%I:%M %p")

        preview = (
            f"\u25cb AWAITING \u00b7 CALENDAR\n"
            f"Here's your event summary \u2014 confirm to add to Google Calendar:\n\n"
            f"Title     : {fields['title']}\n"
            f"When      : {display_dt}\n"
            f"Duration  : {dur_label}\n"
            f"Timezone  : {config.CALENDAR_TIMEZONE}\n"
            f"Reminders : 10 min before \u00b7 1 day before\n\n"
            f"Confirm creating this event? (yes / no)\n"
            f"\u2713 Confirm   \u2715 Cancel"
        )
        session.awaiting_confirmation = True
        flow["awaiting_confirmation"] = True
        flow["confirmation_payload"] = {**fields, "datetime": event_dt.isoformat()}
        session.flow = flow
        duration_hours = max(1, (duration + 59) // 60)
        memory_plan = {
            "action": "calendar",
            "arguments": {
                "title": fields["title"],
                "datetime_phrase": event_dt.strftime("%Y-%m-%d %H:%M"),
                "duration": duration_hours,
            },
            "missing_fields": [],
        }
        session.memory.set_pending_action(memory_plan)
        _remember_turn(session.memory, user_message, preview)
        return _r("awaiting", "calendar", preview,
                  preview={"title": fields["title"], "datetime": display_dt, "duration": duration_hours})

    return _r("error", "calendar", "Unexpected calendar flow state.")


# ═══════════════════════════════════════════════════════════════
# CHANGE 12 — Execute confirmed action
# ═══════════════════════════════════════════════════════════════

def execute_confirmed_action(session: Session, user_id: str = None, db=None) -> ChatResponse:
    # FIXED: BUG-E1, BUG-C2 — only execute after yes confirmation with real API
    flow = session.flow
    action = flow.get("pending_action") or (
        session.memory.pending_action.get("action") if session.memory.pending_action else None
    )
    payload = flow.get("confirmation_payload", {})

    if action == "email":
        try:
            to = payload["to"]
            if isinstance(to, list):
                to = to[0]
            result = send_email(
                to=to,
                subject=payload["subject"],
                body=payload["body"],
                user_id=user_id,
                db=db,
            )
            clear_pending_state(session)
            try:
                _require_real_execution("email", result)
            except RuntimeError as exc:
                log.error(str(exc))
                return _r("error", "email",
                          "Email could not be sent: internal execution guard triggered.")
            if result["status"] == "success":
                msg = (
                    f"\u2713 Email sent successfully to {to}.\n"
                    f"Subject: {payload['subject']}"
                )
                return _r("success", "email", msg)
            return _r("error", "email",
                        f"\u2717 Failed to send email: {result.get('message', 'Unknown error')}.\n"
                        "Please check your Gmail connection.")
        except Exception as e:
            clear_pending_state(session)
            return _r("error", "email", f"\u2717 Email error: {str(e)}")

    if action == "calendar":
        try:
            event_dt = datetime.fromisoformat(payload["datetime"])
            duration_min = payload.get("duration", 60)
            duration_hours = max(1, (duration_min + 59) // 60)
            description = draft_event_description(payload["title"], payload["title"])
            result = create_calendar_event(
                title=payload["title"],
                date=event_dt.strftime("%Y-%m-%d"),
                time=event_dt.strftime("%H:%M"),
                duration_hours=duration_hours,
                description=description,
                user_id=user_id,
                db=db,
            )
            clear_pending_state(session)
            try:
                _require_real_execution("calendar", result)
            except RuntimeError as exc:
                log.error(str(exc))
                return _r("error", "calendar",
                          "Calendar event could not be created: internal execution guard triggered.")
            if result["status"] == "success":
                link = result.get("event_link", "Google Calendar")
                msg = (
                    f"\u2713 Event created: '{payload['title']}'\n"
                    f"  When: {event_dt.strftime('%A, %d %B %Y at %I:%M %p')}\n"
                    f"  Duration: {duration_hours} hour{'s' if duration_hours != 1 else ''}\n"
                    f"  View: {link}"
                )
                return _r("success", "calendar", msg)
            return _r("error", "calendar",
                        f"\u2717 Failed to create event: {result.get('message', 'Unknown error')}.\n"
                        "Please check your Google Calendar connection.")
        except Exception as e:
            clear_pending_state(session)
            return _r("error", "calendar", f"\u2717 Calendar error: {str(e)}")

    clear_pending_state(session)
    return _r("error", "none", "No pending action to confirm.")


# ═══════════════════════════════════════════════════════════════
# Direct execution helpers (weather, news, search, summarize)
# ═══════════════════════════════════════════════════════════════

def _execute_plan(plan: dict, user_id: str = None, db=None) -> ChatResponse:
    action = plan["action"]
    args = plan.get("arguments", {})

    if action == "summarize":
        result = summarize(
            content=args.get("content", ""),
            url=args.get("url", ""),
            file_path=args.get("file_path", ""),
        )
        return _r("success", "summarize", result)

    if action == "news":
        articles, topic = fetch_raw_news(args.get("topic", "general"))
        if not articles:
            return _r("error", "news", f"No news found for '{topic}'.")
        count = len(articles)
        summary_msg = f"Latest {count} headline{'s' if count != 1 else ''} on '{topic}'."
        return _r("success", "news", summary_msg,
                  news_articles=[
                      NewsArticle(
                          title=a["title"],
                          description=a.get("description"),
                          source=a["source"],
                          published=a.get("published", ""),
                          url=a.get("url", ""),
                      )
                      for a in articles
                  ])

    if action == "weather":
        result = fetch_weather(args.get("city", ""))
        if result["status"] == "success":
            return _r("success", "weather", result["message"])
        return _r("error", "weather", result["message"])

    if action == "web_search":
        result = search_web(args.get("query", ""))
        if result["status"] == "success":
            return _r("success", "web_search", result["message"])
        return _r("error", "web_search", result["message"])

    return _r("error", "none", "Unknown action.")


def _store_last_result(session: Session, action: str, message: str) -> None:
    session.last_result = {
        "type": action,
        "data": message,
        "summary": message[:200] if message else "",
        "timestamp": time.time(),
    }


# ═══════════════════════════════════════════════════════════════
# MAIN PROCESS — 7-step pipeline
# ═══════════════════════════════════════════════════════════════

def process(
    message: str,
    session: Session,
    file_path: str = None,
    selected_services: list = None,
    user_id: str = None,
    db=None,
) -> ChatResponse:
    memory = session.memory
    selected_services = selected_services or []
    all_user_messages = _get_user_messages(memory)
    flow = session.flow

    # STEP 0: Pre-classify + clear stale pending on strong new intent
    # FIXED: BUG-I4, BUG-I5 — new intent overrides stale pending state
    pre_intent = pre_classify_intent(message)

    if pre_intent and pre_intent not in ("cancel", None):
        pending = flow.get("pending_action")
        if pending and pre_intent != pending:
            clear_pending_state(session)
            flow = session.flow

    # STEP 1: Confirmation gate (only when truly awaiting)
    # FIXED: BUG-E1 — email/calendar never execute without yes
    if session.awaiting_confirmation and flow.get("pending_action"):
        conf = _detect_confirmation_response(message)
        if not conf:
            conf_raw = detect_confirmation(
                message, flow.get("pending_action", "action"),
            )
            if conf_raw == "confirm":
                conf = "yes"
            elif conf_raw == "cancel":
                conf = "no"

        if conf == "yes":
            response = execute_confirmed_action(session, user_id=user_id, db=db)
            _remember_turn(memory, message, response.message)
            return response

        if conf == "no":
            clear_pending_state(session)
            msg = "Action cancelled."
            _remember_turn(memory, message, msg)
            return _r("cancelled", "none", msg)

    # Continue pending email/calendar collection (same action, no new strong intent)
    pending = flow.get("pending_action")
    if pending in ("email", "calendar") and not session.awaiting_confirmation:
        if not pre_intent or pre_intent == pending:
            if pending == "email":
                return handle_email_flow(message, session)
            return handle_calendar_flow(message, session)

    # STEP 2: Pure cancel word, or cancel signal while a flow is active
    if pre_intent == "cancel" or (pending and detect_cancel_signal(message)):
        clear_pending_state(session)
        msg = "Action cancelled."
        _remember_turn(memory, message, msg)
        return _r("cancelled", "none", msg)

    # STEP 3: Greeting
    if pre_intent == "greeting":
        _remember_turn(memory, message, _GREETING_RESPONSE)
        return handle_greeting()

    # Capability query (no LLM)
    if _is_capability_query(message):
        _remember_turn(memory, message, _CAPABILITY_RESPONSE)
        return _r("success", "rag", _CAPABILITY_RESPONSE)

    # STEP 4: Classify intent (regex or LLM)
    intent = pre_intent
    plan = None
    if not intent:
        history = memory.get_buffer()
        plan = plan_action(message, history=history[-6:], selected_services=selected_services)
        intent = plan.get("action", "rag")

    # STEP 5: Route
    if intent == "cancel":
        clear_pending_state(session)
        msg = "Action cancelled."
        _remember_turn(memory, message, msg)
        return _r("cancelled", "none", msg)

    if intent == "greeting":
        _remember_turn(memory, message, _GREETING_RESPONSE)
        return handle_greeting()

    if intent == "email":
        return handle_email_flow(message, session)

    if intent == "calendar":
        return handle_calendar_flow(message, session)

    if intent == "weather":
        city = extract_location(message)
        if plan and plan.get("arguments", {}).get("city"):
            city = plan["arguments"]["city"]
        result = fetch_weather(city)
        if result["status"] == "success":
            _store_last_result(session, "weather", result["message"])
            _remember_turn(memory, message, result["message"])
            return _r("success", "weather", result["message"])
        _remember_turn(memory, message, result["message"])
        return _r("error", "weather", result["message"])

    if intent == "news":
        topic = extract_topic(message)
        if plan and plan.get("arguments", {}).get("topic"):
            topic = plan["arguments"]["topic"]
        response = _execute_plan({"action": "news", "arguments": {"topic": topic}}, user_id, db)
        if response.status == "success":
            _store_last_result(session, "news", response.message)
        _remember_turn(memory, message, response.message)
        return response

    if intent == "web_search":
        query = message
        if plan and plan.get("arguments", {}).get("query"):
            query = plan["arguments"]["query"]
        response = _execute_plan({"action": "web_search", "arguments": {"query": query}}, user_id, db)
        if response.status == "success":
            _store_last_result(session, "search", response.message)
        _remember_turn(memory, message, response.message)
        return response

    if intent == "summarize":
        args = (plan or {}).get("arguments", {})
        if file_path:
            args["file_path"] = file_path
        validated = validate_action(
            {"action": "summarize", "arguments": args},
            user_message=message,
            all_user_messages=all_user_messages,
        )
        if validated["missing_fields"]:
            prompt = "Please upload a file, paste a URL, or share the text you'd like me to summarize."
            _remember_turn(memory, message, prompt)
            return _r("pending", "summarize", prompt)
        response = _execute_plan(validated, user_id, db)
        clear_pending_state(session)
        _remember_turn(memory, message, response.message)
        return response

    # RAG fallback — never for email/calendar (blocked by pre-classifier + routing above)
    # FIXED: BUG-I1, BUG-I2 — RAG must not handle email/calendar
    clear_pending_state(session)
    reply = run_rag(message, memory)
    return _r("success", "rag", reply)
