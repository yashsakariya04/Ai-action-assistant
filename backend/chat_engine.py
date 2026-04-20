"""
chat_engine.py — Core logic: processes one message and returns a structured response.
"""

import config
from core.llm_service import (
    plan_action,
    generate_missing_field_prompt,
    detect_confirmation,
    draft_email,
    draft_event_description,
)
from core.action_controller import validate_action
from services.news_service import fetch_raw_news
from services.weather_service import fetch_weather
from services.web_search_service import search_web
from services.email_service import send_email
from services.calendar_service import create_calendar_event
from core.intent_parser import extract_datetime
from core.rag_pipeline import run_rag
from backend.session_store import Session  # noqa: F401
from backend.schemas import ChatResponse, NewsArticle
from services.summarizer_service import summarize


def _r(status: str, action: str, message: str, **kwargs) -> ChatResponse:
    return ChatResponse(status=status, action=action, message=message, **kwargs)


def _get_user_messages(memory) -> list:
    return [
        m["content"]
        for m in memory.get_buffer()
        if m.get("role") == "user" and m.get("content")
    ]


def _ensure_email_body(args: dict, original_message: str) -> dict:
    if not args.get("body") or not args.get("subject"):
        recipient = args.get("recipient_name", "")
        drafted = draft_email(recipient_name=recipient, context=original_message)
        if not args.get("subject"):
            args["subject"] = drafted.get("subject", "Message")
        if not args.get("body"):
            args["body"] = drafted.get("body", "")
    return args


# ─────────────────────────────────────────────────────────────
# EXECUTE
# ─────────────────────────────────────────────────────────────

def _execute(plan: dict, user_id: str = None, db=None) -> ChatResponse:
    action = plan["action"]
    args   = plan.get("arguments", {})

    # ── EMAIL ────────────────────────────────────────────────
    if action == "email":
        to = args.get("to", [])
        if isinstance(to, str):
            to = [to]
        result = send_email(to=to, subject=args["subject"], body=args["body"],
                            user_id=user_id, db=db)
        if result["status"] == "success":
            return _r("success", "email",
                f"Your email has been sent successfully! ✉️\n\n"
                f"To      : {', '.join(to)}\n"
                f"Subject : {args['subject']}\n\n"
                f"The recipient should receive it shortly.")
        return _r("error", "email",
            f"Hmm, something went wrong while sending the email.\n\n{result['message']}\n\n"
            f"Please check your Gmail connection and try again.")

    # ── SUMMARIZE ────────────────────────────────────────────
    if action == "summarize":
        result = summarize(
            content=args.get("content", ""),
            url=args.get("url", ""),
            file_path=args.get("file_path", "")
        )
        return _r("success", "summarize", result)

    # ── CALENDAR ─────────────────────────────────────────────
    if action == "calendar":
        parsed = extract_datetime(args.get("datetime_phrase", ""))
        if not parsed:
            return _r("error", "calendar",
                "I couldn't parse that date and time. Could you try something like "
                "'next Friday at 2pm' or 'March 25 at 10:30am'?")

        duration    = max(1, int(args.get("duration", 1) or 1))
        title       = args["title"]
        description = args.get("description", "")
        location    = args.get("location", "")

        if not description:
            description = draft_event_description(title, title)

        result = create_calendar_event(
            title=title,
            date=parsed.strftime("%Y-%m-%d"),
            time=parsed.strftime("%H:%M"),
            duration_hours=duration,
            description=description,
            location=location,
            user_id=user_id,
            db=db,
        )

        if result["status"] == "success":
            display  = parsed.strftime("%A, %B %d %Y")
            end_hour = parsed.hour + duration
            end_time = parsed.replace(hour=end_hour) if end_hour < 24 else parsed
            link     = f"\nEvent Link : {result['event_link']}" if result.get("event_link") else ""

            return _r("success", "calendar",
                f"Your event has been created and added to Google Calendar! 🗓️\n\n"
                f"Title     : {title}\n"
                f"Date      : {display}\n"
                f"Time      : {parsed.strftime('%I:%M %p')} – {end_time.strftime('%I:%M %p')}\n"
                f"Duration  : {duration} hour{'s' if duration != 1 else ''}\n"
                f"Timezone  : {config.CALENDAR_TIMEZONE}\n"
                f"Reminders : 10 min before · 1 day before"
                f"{link}\n\n"
                f"You'll get a reminder so you never miss it.")

        return _r("error", "calendar",
            f"Couldn't create the calendar event.\n\n{result['message']}\n\n"
            f"Please check your Google Calendar connection and try again.")

    # ── NEWS ─────────────────────────────────────────────────
    if action == "news":
        articles, topic = fetch_raw_news(args.get("topic", "general"))
        if not articles:
            return _r("error", "news",
                f"I couldn't find any news or web results for '{topic}' right now. "
                f"Try a broader search term or check back in a moment.")

        is_web_fallback = articles[0].get("source") == "Web Search"
        count = len(articles)

        if is_web_fallback:
            summary_msg = (
                f"No dedicated news articles found for '{topic}', so I pulled the best web results instead. "
                f"Here are {count} relevant result{'s' if count != 1 else ''} — hope this helps!"
            )
        else:
            summary_msg = (
                f"Here are the latest {count} headline{'s' if count != 1 else ''} on '{topic}'. "
                f"Stay informed! 📰"
            )

        return _r("success", "news",
            summary_msg,
            news_articles=[
                NewsArticle(
                    title=a["title"],
                    description=a.get("description"),
                    source=a["source"],
                    published=a.get("published", ""),
                    url=a.get("url", ""),
                )
                for a in articles
            ],
        )

    # ── WEATHER ──────────────────────────────────────────────
    if action == "weather":
        city   = args.get("city", "")
        result = fetch_weather(city)
        if result["status"] == "success":
            return _r("success", "weather", result["message"])
        return _r("error", "weather", result["message"])

    # ── WEB SEARCH ───────────────────────────────────────────
    if action == "web_search":
        query  = args.get("query", "")
        result = search_web(query)
        if result["status"] == "success":
            return _r("success", "web_search", result["message"])
        return _r("error", "web_search", result["message"])

    return _r("error", "none", "Unknown action.")


# ─────────────────────────────────────────────────────────────
# PREVIEW — confirmation card
# ─────────────────────────────────────────────────────────────

def _preview(plan: dict, original_message: str) -> ChatResponse:
    action = plan["action"]
    args   = plan.get("arguments", {})

    if action == "email":
        to = args.get("to", [])
        if isinstance(to, str):
            to = [to]
        subject = args.get("subject", "")
        body    = args.get("body", "")

        preview_text = (
            f"Here's your email, ready to go. Give it a quick look before I send it!\n\n"
            f"To      : {', '.join(to)}\n"
            f"Subject : {subject}\n"
            f"{'-' * 44}\n"
            f"{body}\n"
            f"{'-' * 44}\n\n"
            f"Confirm sending this email? (yes / no)"
        )
        return _r("awaiting", "email", preview_text,
            preview={"to": to, "subject": subject, "body": body})

    if action == "calendar":
        parsed     = extract_datetime(args.get("datetime_phrase", ""))
        display_dt = (parsed.strftime("%A, %B %d %Y at %I:%M %p")
                      if parsed else args.get("datetime_phrase", ""))
        duration    = args.get("duration", 1)
        title       = args.get("title", "")
        location    = args.get("location", "")
        description = args.get("description", "")

        loc_line  = f"\nLocation  : {location}" if location else ""
        desc_line = (
            f"\nAgenda    : {description[:100]}…"
            if len(description) > 100
            else (f"\nAgenda    : {description}" if description else "")
        )

        preview_text = (
            f"Here's your event summary — looks good? I'll add it to your Google Calendar!\n\n"
            f"Title     : {title}\n"
            f"When      : {display_dt}\n"
            f"Duration  : {duration} hour{'s' if duration != 1 else ''}\n"
            f"Timezone  : {config.CALENDAR_TIMEZONE}"
            f"{loc_line}"
            f"{desc_line}\n"
            f"Reminders : 10 min before · 1 day before\n\n"
            f"Confirm creating this event? (yes / no)"
        )
        return _r("awaiting", "calendar", preview_text,
            preview={"title": title, "datetime": display_dt, "duration": duration,
                     "timezone": config.CALENDAR_TIMEZONE, "location": location})

    return _r("awaiting", action, "Ready to proceed. Confirm? (yes / no)")


# ─────────────────────────────────────────────────────────────
# PROCESS — called by /chat endpoint and MCP tools
# ─────────────────────────────────────────────────────────────

def process(message: str, session: Session, file_path: str = None,
            selected_services: list = None, user_id: str = None, db=None) -> ChatResponse:
    memory = session.memory
    selected_services = selected_services or []

    all_user_messages = _get_user_messages(memory)

    # 1. CONFIRMATION CHECK
    if session.awaiting_confirmation and memory.pending_action:
        pending_action_type = memory.pending_action.get("action", "action")
        intent = detect_confirmation(message, pending_action_type)

        if intent == "confirm":
            session.awaiting_confirmation = False
            response = _execute(memory.pending_action, user_id=user_id, db=db)
            memory.clear_pending_action()
            memory.add("user", message)
            memory.add("assistant", response.message)
            return response

        if intent == "cancel":
            session.awaiting_confirmation = False
            memory.clear_pending_action()
            msg = "No problem — action cancelled. What else can I help you with?"
            memory.add("user", message)
            memory.add("assistant", msg)
            return _r("cancelled", "none", msg)

        session.awaiting_confirmation = False

    # 2. PLAN
    history = memory.get_buffer()
    plan = plan_action(message, history=history, selected_services=selected_services)
    plan = memory.merge_action_arguments(plan)

    if file_path:
        plan["arguments"]["file_path"] = file_path

    # 3. VALIDATE
    plan = validate_action(
        plan,
        user_message=message,
        all_user_messages=all_user_messages,
    )
    action = plan["action"]

    # 4. RAG
    if action == "rag":
        memory.clear_pending_action()
        reply = run_rag(message, memory)
        return _r("success", "rag", reply)

    # 5. DIRECT EXECUTION (no confirmation needed)
    if action in ("news", "weather", "web_search"):
        response = _execute(plan, user_id=user_id, db=db)
        memory.clear_pending_action()
        memory.add("user", message)
        memory.add("assistant", response.message)
        return response

    # 5d. SUMMARIZE
    if action == "summarize":
        args = plan.get("arguments", {})
        has_source = args.get("file_path") or args.get("url") or args.get("content")
        if not has_source:
            prompt = "Sure! Please upload a file, paste a URL, or share the text you'd like me to summarize."
            memory.add("user", message)
            memory.add("assistant", prompt)
            return _r("pending", "summarize", prompt)

        response = _execute(plan, user_id=user_id, db=db)
        memory.clear_pending_action()
        memory.add("user", message)
        memory.add("assistant", response.message)
        return response

    # 6. EMAIL — auto-draft body/subject
    if action == "email":
        args = plan.get("arguments", {})
        if args.get("recipient_name") and not args.get("body"):
            args = _ensure_email_body(args, message)
            plan["arguments"] = args
        plan = validate_action(
            plan,
            user_message=message,
            all_user_messages=all_user_messages,
        )

    # 7. MISSING FIELDS
    if plan["missing_fields"]:
        memory.set_pending_action(plan)
        prompt = generate_missing_field_prompt(
            action=action,
            missing_fields=plan["missing_fields"],
            current_args=plan.get("arguments", {}),
            history=history,
        )
        memory.add("user", message)
        memory.add("assistant", prompt)
        return _r("pending", action, prompt)

    # 8. PREVIEW + CONFIRM
    memory.set_pending_action(plan)
    session.awaiting_confirmation = True
    response = _preview(plan, message)
    memory.add("user", message)
    memory.add("assistant", response.message)
    return response
