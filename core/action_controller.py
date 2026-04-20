"""
action_controller.py — Validate required fields before execution.
Now uses validators.py for strict anti-hallucination checks.
"""

import logging
from typing import Dict, List, Optional

from core.validators import (
    validate_email_action,
    validate_calendar_action,
    validate_weather_action,
    validate_web_search_action,
    validate_summarize_action,
)

log = logging.getLogger(__name__)

# Required fields per action type
REQUIRED_FIELDS = {
    "email":    ["to", "subject", "body"],
    "calendar": ["title", "datetime_phrase"],
    "news":     [],
    "weather":  ["city"],
    "web_search": ["query"],
    "rag":      [],
    "summarize": []
}


def validate_action(
    plan: Dict,
    user_message: str = "",
    all_user_messages: Optional[List[str]] = None,
) -> Dict:
    """
    Validate a planned action — checks field existence AND content validity.

    Args:
        plan: The action plan from the LLM planner.
        user_message: The current user message (for email verification).
        all_user_messages: All user messages in the conversation
                          (for multi-turn email address verification).

    Returns:
        Validated plan dict with:
        - "action": the action type
        - "arguments": cleaned arguments (fabricated data stripped)
        - "missing_fields": fields still needed from user
        - "ready_for_confirmation": True if all fields are valid
        - "validation_errors": list of human-readable error messages
    """
    action    = plan.get("action", "rag")
    arguments = plan.get("arguments", {}) or {}

    validated = {
        "action":                 action,
        "arguments":              arguments,
        "missing_fields":         [],
        "ready_for_confirmation": False,
        "validation_errors":      [],
    }

    # ── EMAIL: Use strict validators ─────────────────────────
    if action == "email":
        cleaned, missing, errors = validate_email_action(
            arguments, user_message, all_user_messages
        )
        validated["arguments"]         = cleaned
        validated["missing_fields"]    = missing
        validated["validation_errors"] = errors
        validated["ready_for_confirmation"] = not missing

        return validated

    # ── CALENDAR: Use strict validators ──────────────────────
    if action == "calendar":
        cleaned, missing, errors = validate_calendar_action(arguments)
        validated["arguments"]         = cleaned
        validated["missing_fields"]    = missing
        validated["validation_errors"] = errors
        validated["ready_for_confirmation"] = not missing

        return validated

    # ── WEATHER ──────────────────────────────────────────────
    if action == "weather":
        cleaned, missing, errors = validate_weather_action(arguments)
        validated["arguments"]         = cleaned
        validated["missing_fields"]    = missing
        validated["validation_errors"] = errors
        validated["ready_for_confirmation"] = not missing
        return validated

    # ── WEB SEARCH ───────────────────────────────────────────
    if action == "web_search":
        cleaned, missing, errors = validate_web_search_action(arguments)
        validated["arguments"]         = cleaned
        validated["missing_fields"]    = missing
        validated["validation_errors"] = errors
        validated["ready_for_confirmation"] = not missing
        return validated

    # ── SUMMARIZE ────────────────────────────────────────────
    if action == "summarize":
        cleaned, missing, errors = validate_summarize_action(arguments)
        validated["arguments"]         = cleaned
        validated["missing_fields"]    = missing
        validated["validation_errors"] = errors
        validated["ready_for_confirmation"] = not missing
        return validated

    # ── NEWS / RAG: No required fields, always ready ─────────
    validated["ready_for_confirmation"] = True
    return validated