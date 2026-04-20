"""
calendar_service.py — Google Calendar event creation with reminders and description.
"""

import logging
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

log = logging.getLogger(__name__)


def _get_calendar_service(user_id: str = None, db=None):
    if user_id and db:
        from backend.google_auth import get_user_credentials
        creds = get_user_credentials(user_id, db)
        if creds:
            return build("calendar", "v3", credentials=creds, cache_discovery=False)
        raise PermissionError(
            "Your Google account is not connected. "
            "Please click 'Connect Google' in the sidebar to authorize Gmail and Calendar access."
        )
    # Fallback to shared credentials
    from scripts.calendar_auth import get_credentials
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_calendar_event(
    title: str,
    date: str,
    time: str,
    duration_hours: int = 1,
    description: str = "",
    location: str = "",
    user_id: str = None,
    db=None,
) -> dict:
    """
    Create a Google Calendar event with reminders and optional description.

    Args:
        title          : Event summary/title
        date           : "YYYY-MM-DD"
        time           : "HH:MM" 24-hr
        duration_hours : Length of event in hours
        description    : Agenda / notes (formatted text)
        location       : Location or meeting link

    Returns:
        {"status": "success"|"error", "message", "event_id", "event_link"}
    """
    if not title:
        return {"status": "error", "message": "Event title is missing."}
    if not date or not time:
        return {"status": "error", "message": "Date or time is missing."}

    try:
        start_time = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return {"status": "error", "message": "Invalid date/time. Expected YYYY-MM-DD and HH:MM."}

    try:
        service = _get_calendar_service(user_id=user_id, db=db)

        end_time = start_time + timedelta(hours=max(1, duration_hours))

        event_body = {
            "summary":     title,
            "description": description,
            "location":    location,
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": config.CALENDAR_TIMEZONE,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": config.CALENDAR_TIMEZONE,
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup",  "minutes": 10},
                    {"method": "email",  "minutes": 1440},  # 1 day
                ],
            },
        }

        created    = service.events().insert(calendarId="primary", body=event_body).execute()
        event_id   = created.get("id", "")
        event_link = created.get("htmlLink", "")
        log.info("Calendar event created: %s (%s)", title, event_id)

        return {
            "status":     "success",
            "message":    f"Event '{title}' created for {start_time.strftime('%B %d, %Y at %H:%M')} ({config.CALENDAR_TIMEZONE}).",
            "event_id":   event_id,
            "event_link": event_link,
        }

    except PermissionError as exc:
        return {"status": "error", "message": str(exc)}
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}
    except HttpError as exc:
        return {"status": "error", "message": f"Google Calendar API error: {exc.reason}"}
    except Exception as exc:
        log.exception("Unexpected calendar error")
        return {"status": "error", "message": f"Failed to create event: {exc}"}
