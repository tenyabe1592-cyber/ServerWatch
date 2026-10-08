from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings
from .database import Database


def send_notification(settings: Settings, db: Database, incident_id: int | None, subject: str, body: str) -> bool:
    if not settings.notifications_configured:
        db.record_notification(incident_id, 0, "skipped", "SMTP is not configured")
        return False

    message = EmailMessage()
    message["Subject"] = f"[ServerWatch] {subject}"
    message["From"] = settings.smtp_from
    message["To"] = settings.smtp_to
    message.set_content(body)

    # Two total attempts: the initial attempt and one bounded retry.
    for attempt in (1, 2):
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
            db.record_notification(incident_id, attempt, "sent", "accepted by SMTP server")
            return True
        except (OSError, smtplib.SMTPException) as exc:
            db.record_notification(incident_id, attempt, "failed", f"{type(exc).__name__}: {exc}")
    return False

