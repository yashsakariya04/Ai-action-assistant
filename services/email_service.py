"""
email_service.py — Gmail API integration (replaces SMTP).

Uses the same credentials.json + token.pickle OAuth flow already
set up in the project for Google Calendar. No new credentials needed.

Advantages over SMTP:
  - No App Password needed
  - More reliable delivery
  - Supports HTML emails
  - Better error messages
  - Same OAuth token as Calendar (already authorized)

Scopes required (add to calendar_auth.py if re-authorizing):
  https://www.googleapis.com/auth/gmail.send
"""

import base64
import logging
import os
import pickle
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Union

import config

log = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _get_gmail_service(user_id: str = None, db=None):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    # ── Per-user credentials from DB ──
    if user_id and db:
        from backend.google_auth import get_user_credentials
        creds = get_user_credentials(user_id, db)
        if creds:
            return build("gmail", "v1", credentials=creds)
        raise PermissionError(
            "Your Google account is not connected. "
            "Please click 'Connect Google' in the sidebar to authorize Gmail and Calendar access."
        )

    # ── Fallback: single shared token.pickle (legacy / admin) ──
    from google_auth_oauthlib.flow import InstalledAppFlow
    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.send",
    ]
    creds = None
    token_file = config.GOOGLE_TOKEN_FILE
    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_file, "wb") as f:
                pickle.dump(creds, f)
        except Exception as exc:
            log.warning("Token refresh failed: %s", exc)
            creds = None
    if not creds or not creds.valid:
        if not os.path.exists(config.GOOGLE_CREDENTIALS_FILE):
            raise FileNotFoundError(f"credentials.json not found at: {config.GOOGLE_CREDENTIALS_FILE}")
        flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, "wb") as f:
            pickle.dump(creds, f)
    return build("gmail", "v1", credentials=creds)


def send_email(
    to: Union[str, List[str]],
    subject: str,
    body: str,
    user_id: str = None,
    db=None,
) -> Dict:
    """
    Send an email using the Gmail API.

    Args:
        to      : Single email address or list of addresses
        subject : Email subject line
        body    : Plain text email body

    Returns:
        { "status": "success"|"error", "message": str }
    """
    if isinstance(to, str):
        to = [to]
    to = [addr.strip() for addr in to if addr.strip()]

    if not to:
        return {"status": "error", "message": "No recipient email address provided."}
    if not subject or not subject.strip():
        return {"status": "error", "message": "Email subject cannot be empty."}
    if not body or not body.strip():
        return {"status": "error", "message": "Email body cannot be empty."}

    try:
        service = _get_gmail_service(user_id=user_id, db=db)

        msg = MIMEMultipart("alternative")
        msg["To"]      = ", ".join(to)
        msg["Subject"] = subject.strip()
        msg["From"]    = config.EMAIL_USER

        msg.attach(MIMEText(body.strip(), "plain"))

        html_body    = body.strip().replace("\n", "<br>")
        html_content = f"""<html><body>
<div style="font-family:Arial,sans-serif;font-size:14px;color:#333;max-width:600px;">
{html_body}
</div></body></html>"""
        msg.attach(MIMEText(html_content, "html"))

        raw  = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        sent = service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        message_id = sent.get("id", "unknown")
        log.info("Email sent via Gmail API. ID: %s", message_id)

        return {
            "status":  "success",
            "message": f"Email sent successfully. Message ID: {message_id}",
        }

    except PermissionError as exc:
        return {"status": "error", "message": str(exc)}
    except FileNotFoundError as exc:
        return {"status": "error", "message": str(exc)}

    except Exception as exc:
        err = str(exc).lower()
        if "insufficient permission" in err or "forbidden" in err:
            return {
                "status": "error",
                "message": (
                    "Gmail permission denied. Delete token.pickle and run "
                    "'python calendar_auth.py' to re-authorize with Gmail scope."
                ),
            }
        if "invalid_grant" in err or "token" in err:
            return {
                "status": "error",
                "message": (
                    "Gmail token expired. Delete token.pickle and run "
                    "'python calendar_auth.py' to re-authorize."
                ),
            }
        log.exception("Gmail API send failed")
        return {"status": "error", "message": f"Failed to send email: {exc}"}