"""
intent_parser.py
================
Robust datetime extraction from natural language phrases.

Handles user input like:
  "next monday at 10am"
  "22 march 2026 12:12pm"
  "tomorrow at 3pm"
  "22 match 2026"  (common typo: match → march)

Strategy (applied in order until one succeeds):
  1. Explicit "next <weekday>" handling — dateparser fails on these
  2. dateparser with PREFER_DATES_FROM=future (best for absolute dates)
  3. dateutil fuzzy parsing (good fallback for ambiguous phrases)
  4. dateparser on the original phrase (before typo correction)

Used by: ai/validators.py, backend/chat_engine.py
"""

import calendar
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

import dateparser
from dateutil.parser import parse as dateutil_parse

log = logging.getLogger(__name__)

# Weekday name → integer (Monday=0)
_WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2,
    "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
}

# Common user typos to correct before parsing
_TYPO_FIXES = {
    r"\bmatch\b":  "march",
    r"\bjanu\b":   "january",
    r"\bfeb\b":    "february",
    r"\baug\b":    "august",
    r"\bsept\b":   "september",
    r"\boct\b":    "october",
    r"\bnov\b":    "november",
    r"\bdec\b":    "december",
}


def _clean_phrase(phrase: str) -> str:
    """
    Apply typo corrections and remove filler words that confuse parsers.
    Preserves the time information (e.g. "at 10am" → "10am").
    """
    cleaned = phrase.strip()

    # Fix typos
    for pattern, replacement in _TYPO_FIXES.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    # Remove "on" when followed by a date (e.g. "on 22 march" → "22 march")
    cleaned = re.sub(r"\bon\s+(\d)", r"\1", cleaned, flags=re.IGNORECASE)

    return cleaned


def _handle_next_weekday(phrase: str, now: datetime) -> Optional[datetime]:
    """
    Explicitly handle "next <weekday> [at <time>]" phrases.
    dateparser often fails or gives wrong results for these.

    Returns a datetime or None if the phrase doesn't match this pattern.
    """
    match = re.match(
        r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(.*)",
        phrase.strip(), re.IGNORECASE,
    )
    if not match:
        return None

    day_name   = match.group(1).lower()
    time_part  = match.group(2).strip()
    target_wd  = _WEEKDAY_MAP[day_name]
    current_wd = now.weekday()

    # Calculate days until the next occurrence of that weekday
    delta = (target_wd - current_wd) % 7
    if delta == 0:
        delta = 7   # "next monday" when today is monday = next week

    base_date = now + timedelta(days=delta)

    # Parse the time portion if present
    if time_part:
        time_parsed = dateparser.parse(
            time_part,
            settings={"RETURN_AS_TIMEZONE_AWARE": False},
        )
        if time_parsed:
            return base_date.replace(
                hour=time_parsed.hour,
                minute=time_parsed.minute,
                second=0, microsecond=0,
            )

    # Default to 9:00 AM if no time given
    return base_date.replace(hour=9, minute=0, second=0, microsecond=0)


def extract_datetime(phrase: str) -> Optional[datetime]:
    """
    Extract a datetime from a natural language phrase.

    Applies multiple parsing strategies with typo correction and
    relative phrase handling. Returns None if no valid datetime found.

    Args:
        phrase: Any natural language time expression typed by the user.

    Returns:
        A datetime object, or None if parsing fails entirely.

    Examples:
        "next monday at 10am"          → next Monday at 10:00 AM
        "22 march 2026 12:12pm"        → March 22 2026 at 12:12 PM
        "22 match 2026 on 12:00 PM"    → March 22 2026 at 12:00 PM  (typo fixed)
        "tomorrow at 3pm"              → tomorrow at 3:00 PM
        "march 22 2026 at 12pm"        → March 22 2026 at 12:00 PM
    """
    if not phrase or not phrase.strip():
        return None

    now     = datetime.now()
    cleaned = _clean_phrase(phrase)

    # Strategy 1: Handle "next <weekday>" explicitly
    result = _handle_next_weekday(cleaned, now)
    if result:
        log.debug("intent_parser: next-weekday strategy → %s", result)
        return result

    # Strategy 2: dateparser with future preference (best for absolute dates)
    result = dateparser.parse(
        cleaned,
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )
    if result:
        log.debug("intent_parser: dateparser (future) → %s", result)
        return result

    # Strategy 3: dateutil fuzzy (handles ambiguous/messy phrases)
    try:
        result = dateutil_parse(cleaned, default=now, fuzzy=True)
        # dateutil returns "now" for total failures — reject if too close
        if abs((result - now).total_seconds()) > 60:
            log.debug("intent_parser: dateutil fuzzy → %s", result)
            return result
    except Exception:
        pass

    # Strategy 4: Try the original phrase without typo correction
    if cleaned != phrase.strip():
        result = dateparser.parse(
            phrase.strip(),
            settings={"PREFER_DATES_FROM": "future", "RETURN_AS_TIMEZONE_AWARE": False},
        )
        if result:
            log.debug("intent_parser: dateparser (original) → %s", result)
            return result

    log.warning("intent_parser: could not parse '%s'", phrase)
    return None