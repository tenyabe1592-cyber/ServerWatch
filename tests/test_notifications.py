from pathlib import Path
from unittest.mock import patch

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

