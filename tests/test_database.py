from pathlib import Path

from serverwatch.backup import backup
from serverwatch.database import Database
from serverwatch.restore import restore


def test_incident_deduplication_resolution_and_persistence(tmp_path: Path):
    path = tmp_path / "db.sqlite"
    db = Database(path)
    first, created = db.open_incident("cpu", "High CPU", ">=90", "95")
    second, created_again = db.open_incident("cpu", "High CPU", ">=90", "98")
    assert first == second and created and not created_again
    assert db.resolve_incident("cpu")
    db.close()
    reopened = Database(path)
    assert reopened.incidents()[0]["status"] == "resolved"
    reopened.close()


def test_backup_and_restore(tmp_path: Path):
    source = tmp_path / "source.db"
    db = Database(source)
    db.add_metric(1, 2, 3)
    db.close()
    saved = backup(source, tmp_path / "backups")
    restored = tmp_path / "restored.db"
    restore(saved, restored)
    db2 = Database(restored)
    assert db2.latest_metric()["disk_percent"] == 3
    db2.close()

