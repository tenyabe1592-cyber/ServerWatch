from pathlib import Path
from unittest.mock import MagicMock, patch

from serverwatch.config import Settings
from serverwatch.database import Database
from serverwatch.notifications import send_notification


def test_notification_retries_are_bounded_and_visible(tmp_path: Path):
    settings = Settings(
        db_path=tmp_path / "db.sqlite", smtp_host="smtp.example", smtp_from="from@example", smtp_to="to@example"
    )
    db = Database(settings.db_path)
    with patch("serverwatch.notifications.smtplib.SMTP", side_effect=OSError("offline")) as smtp:
        assert not send_notification(settings, db, None, "Test", "Body")
    assert smtp.call_count == 2
    attempts = db.notification_attempts()
    assert len(attempts) == 2 and all(row["status"] == "failed" for row in attempts)
    db.close()


def test_notification_prefers_login_challenge_response(tmp_path: Path):
    settings = Settings(
        db_path=tmp_path / "db.sqlite",
        smtp_host="smtp.example",
        smtp_username="sender@example",
        smtp_password="app-password",
        smtp_from="sender@example",
        smtp_to="recipient@example",
    )
    db = Database(settings.db_path)
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.esmtp_features = {"auth": "LOGIN PLAIN"}

    with patch("serverwatch.notifications.smtplib.SMTP", return_value=connection):
        assert send_notification(settings, db, None, "Test", "Body")

    connection.starttls.assert_called_once_with()
    connection.ehlo.assert_called_once_with()
    mechanism, response = connection.auth.call_args.args
    assert mechanism == "LOGIN"
    assert connection.auth.call_args.kwargs == {"initial_response_ok": False}
    assert response(b"Username:") == settings.smtp_username
    assert response(b"Password:") == settings.smtp_password
    connection.send_message.assert_called_once()
    attempts = db.notification_attempts()
    assert len(attempts) == 1 and attempts[0]["status"] == "sent"
    db.close()
