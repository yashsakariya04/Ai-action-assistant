"""
validators.py — Strict validation layer to prevent LLM hallucination.

CORE PRINCIPLE: Never trust LLM-generated critical data.
  - Email addresses MUST come from user's actual message, not LLM invention
  - Dates MUST be parseable and in the future
  - Bodies/subjects CAN be LLM-drafted (that's the feature) but shown for approval

This module is used by action_controller.py and mcp_server.py.
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, List

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# EMAIL VALIDATION
# ─────────────────────────────────────────────────────────────

# RFC 5322 simplified — strict enough to block garbage, permissive enough for real addresses
_EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
    r"@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,}$"
)

# Pattern to find email-like strings in text
_EMAIL_FINDER = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)


def is_valid_email_format(email: str) -> bool:
    """Check if an email string has valid format."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if len(email) > 254:
        return False
    return _EMAIL_REGEX.fullmatch(email) is not None


def extract_emails_from_text(text: str) -> List[str]:
    """Extract all email-like strings from user text."""
    if not text:
        return []
    return _EMAIL_FINDER.findall(text)


def validate_email_address(
    email: str,
    user_message: str,
    all_user_messages: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Validate an email address is both well-formed AND came from the user.

    Args:
        email: The email address to validate.
        user_message: The current user message to check against.
        all_user_messages: Optional list of all user messages in conversation
                          (for multi-turn field collection).

    Returns:
        (is_valid, error_reason)
        is_valid=True  → email is safe to use
        is_valid=False → error_reason explains why
    """
    email = email.strip() if email else ""

    # 1. Format check
    if not is_valid_email_format(email):
        return False, f"'{email}' is not a valid email format."

    # 2. CRITICAL: Verify the email was typed by the user, not fabricated by LLM
    messages_to_search = [user_message]
    if all_user_messages:
        messages_to_search.extend(all_user_messages)

    user_provided = False
    for msg in messages_to_search:
        if not msg:
            continue
        # Check if this exact email appears in any user message
        emails_in_msg = extract_emails_from_text(msg)
        if email.lower() in [e.lower() for e in emails_in_msg]:
            user_provided = True
            break

    if not user_provided:
        return False, (
            f"Email '{email}' was not found in the user's messages. "
            f"The system cannot use email addresses that the user did not explicitly provide."
        )

    return True, ""


def validate_email_list(
    emails: list,
    user_message: str,
    all_user_messages: Optional[List[str]] = None,
) -> Tuple[List[str], List[str], str]:
    """
    Validate a list of email addresses.

    Returns:
        (valid_emails, invalid_emails, error_message)
    """
    if not emails:
        return [], [], "No email addresses provided."

    valid = []
    invalid = []
    errors = []

    for email in emails:
        is_ok, reason = validate_email_address(
            email, user_message, all_user_messages
        )
        if is_ok:
            valid.append(email)
        else:
            invalid.append(email)
            errors.append(reason)

    error_msg = "; ".join(errors) if errors else ""
    return valid, invalid, error_msg


# ─────────────────────────────────────────────────────────────
# CALENDAR VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_datetime_phrase(phrase: str) -> Tuple[bool, Optional[datetime], str]:
    """
    Validate that a datetime phrase is parseable and represents a future time.

    Returns:
        (is_valid, parsed_datetime, error_reason)
    """
    if not phrase or not phrase.strip():
        return False, None, "No date/time phrase provided."

    from core.intent_parser import extract_datetime

    try:
        parsed = extract_datetime(phrase)
    except Exception as exc:
        return False, None, f"Failed to parse datetime: {exc}"

    if not parsed:
        return False, None, (
            f"Could not understand the date/time from: '{phrase}'. "
            f"Please try formats like 'next Friday at 2pm', "
            f"'tomorrow at 10am', or 'March 20 2026 at 3pm'."
        )

    # Allow a small buffer (5 minutes) for "now" type requests
    now = datetime.now()
    if parsed < now - timedelta(minutes=5):
        return False, None, (
            f"The time '{phrase}' appears to be in the past "
            f"({parsed.strftime('%B %d %Y at %I:%M %p')}). "
            f"Please provide a future date and time."
        )

    return True, parsed, ""


def validate_event_title(title: str) -> Tuple[bool, str]:
    """
    Validate that an event title is meaningful.

    Returns:
        (is_valid, error_reason)
    """
    if not title or not title.strip():
        return False, "Event title cannot be empty."

    title = title.strip()

    if len(title) < 3:
        return False, "Event title is too short. Please provide a descriptive title."

    if len(title) > 200:
        return False, "Event title is too long. Please keep it under 200 characters."

    # Reject obvious placeholder titles
    placeholders = {"test", "asdf", "xxx", "tbd", "untitled", "none", "null", "n/a"}
    if title.lower() in placeholders:
        return False, f"'{title}' seems like a placeholder. Please provide a real event title."

    return True, ""


# ─────────────────────────────────────────────────────────────
# EMAIL CONTENT VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_email_body(body: str) -> Tuple[bool, str]:
    """
    Validate email body is real content, not a placeholder.

    Returns:
        (is_valid, error_reason)
    """
    if not body or not body.strip():
        return False, "Email body cannot be empty."

    body = body.strip()

    if len(body) < 10:
        return False, "Email body is too short to be a real message."

    # Check for LLM placeholder patterns
    placeholder_patterns = [
        r"\[INSERT\s",
        r"\[YOUR\s",
        r"\[FILL\s",
        r"\[PLACEHOLDER",
        r"\[TODO",
        r"<INSERT\s",
        r"<YOUR\s",
    ]
    for pattern in placeholder_patterns:
        if re.search(pattern, body, re.IGNORECASE):
            return False, (
                "The email body contains placeholder text. "
                "Please provide the actual content or ask me to draft it."
            )

    return True, ""


def validate_email_subject(subject: str) -> Tuple[bool, str]:
    """
    Validate email subject is meaningful.

    Returns:
        (is_valid, error_reason)
    """
    if not subject or not subject.strip():
        return False, "Email subject cannot be empty."

    subject = subject.strip()

    if len(subject) < 2:
        return False, "Email subject is too short."

    if len(subject) > 200:
        return False, "Email subject is too long. Please keep it under 200 characters."

    return True, ""


# ─────────────────────────────────────────────────────────────
# COMPOSITE VALIDATORS
# ─────────────────────────────────────────────────────────────

def validate_email_action(
    args: dict,
    user_message: str,
    all_user_messages: Optional[List[str]] = None,
) -> Tuple[dict, List[str], List[str]]:
    """
    Validate all fields for an email action.
    STRIPS any LLM-fabricated email addresses.

    Args:
        args: The extracted arguments dict.
        user_message: Current user message.
        all_user_messages: All user messages in conversation.

    Returns:
        (cleaned_args, missing_fields, validation_errors)
        - cleaned_args: args with invalid data stripped out
        - missing_fields: fields that still need user input
        - validation_errors: human-readable error messages
    """
    cleaned = dict(args)
    missing = []
    errors = []

    # ── Validate "to" field ───────────────────────────���──────
    to_list = cleaned.get("to")
    if to_list:
        if isinstance(to_list, str):
            to_list = [to_list]

        valid_emails, invalid_emails, err_msg = validate_email_list(
            to_list, user_message, all_user_messages
        )

        if valid_emails:
            cleaned["to"] = valid_emails
        else:
            # ALL emails were invalid/fabricated — strip the field entirely
            cleaned["to"] = []
            missing.append("to")
            if invalid_emails:
                log.warning(
                    "Stripped LLM-fabricated emails: %s", invalid_emails
                )
    else:
        missing.append("to")

    # ── Validate subject ─────────────────────────────────────
    subject = cleaned.get("subject")
    if subject:
        ok, err = validate_email_subject(subject)
        if not ok:
            errors.append(err)
            cleaned["subject"] = None
            missing.append("subject")
    else:
        missing.append("subject")

    # ── Validate body ────────────────────────────────────────
    body = cleaned.get("body")
    if body:
        ok, err = validate_email_body(body)
        if not ok:
            errors.append(err)
            cleaned["body"] = None
            missing.append("body")
    else:
        missing.append("body")

    return cleaned, missing, errors


def validate_calendar_action(args: dict) -> Tuple[dict, List[str], List[str]]:
    """
    Validate all fields for a calendar action.

    Returns:
        (cleaned_args, missing_fields, validation_errors)
    """
    cleaned = dict(args)
    missing = []
    errors = []

    # ── Validate title ───────────────────────────────────────
    title = cleaned.get("title")
    if title:
        ok, err = validate_event_title(title)
        if not ok:
            errors.append(err)
            cleaned["title"] = None
            missing.append("title")
    else:
        missing.append("title")

    # ── Validate datetime ────────────────────────────────────
    dt_phrase = cleaned.get("datetime_phrase")
    if dt_phrase:
        ok, parsed_dt, err = validate_datetime_phrase(dt_phrase)
        if not ok:
            errors.append(err)
            cleaned["datetime_phrase"] = None
            missing.append("datetime_phrase")
    else:
        missing.append("datetime_phrase")

    # ── Duration sanity check ────────────────────────────────
    duration = cleaned.get("duration")
    if duration is not None:
        try:
            duration = int(duration)
            if duration < 1:
                duration = 1
            if duration > 24:
                errors.append("Duration cannot exceed 24 hours.")
                duration = 24
            cleaned["duration"] = duration
        except (TypeError, ValueError):
            cleaned["duration"] = 1

    return cleaned, missing, errors

# ─────────────────────────────────────────────────────────────
# WEATHER VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_weather_action(args: dict) -> Tuple[dict, List[str], List[str]]:
    """
    Validate all fields for a weather action.

    Returns:
        (cleaned_args, missing_fields, validation_errors)
    """
    cleaned = dict(args)
    missing = []
    errors  = []

    city = cleaned.get("city")
    if not city or not str(city).strip():
        missing.append("city")
    else:
        city = str(city).strip()
        if len(city) < 2:
            errors.append("City name is too short.")
            cleaned["city"] = None
            missing.append("city")
        elif len(city) > 100:
            errors.append("City name is too long.")
            cleaned["city"] = None
            missing.append("city")
        else:
            cleaned["city"] = city

    return cleaned, missing, errors


# ─────────────────────────────────────────────────────────────
# WEB SEARCH VALIDATION
# ─────────────────────────────────────────────────────────────

def validate_web_search_action(args: dict) -> Tuple[dict, List[str], List[str]]:
    """
    Validate all fields for a web_search action.

    Returns:
        (cleaned_args, missing_fields, validation_errors)
    """
    cleaned = dict(args)
    missing = []
    errors  = []

    query = cleaned.get("query")
    if not query or not str(query).strip():
        missing.append("query")
    else:
        query = str(query).strip()
        if len(query) < 2:
            errors.append("Search query is too short.")
            cleaned["query"] = None
            missing.append("query")
        elif len(query) > 300:
            cleaned["query"] = query[:300]   # silently trim
        else:
            cleaned["query"] = query

    return cleaned, missing, errors

def validate_summarize_action(args: dict):
    content = args.get("content")
    url = args.get("url")
    file_path = args.get("file_path")

    if not content and not url and not file_path:
        return args, ["content"], ["Provide text, URL, or file"]

    return args, [], []