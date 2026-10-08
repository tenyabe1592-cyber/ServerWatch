from pathlib import Path
from unittest.mock import patch

import pytest

from serverwatch.config import Settings
from serverwatch.database import Database
from serverwatch.engine import MonitorEngine
from serverwatch.monitor import HealthReading, MetricReading


def test_engine_is_deterministic_and_deduplicates_alerts(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "db.sqlite", test_mode=True, services=("demo.service",), endpoints=())
    db = Database(settings.db_path)
    engine = MonitorEngine(settings, db)
    with (
        patch("serverwatch.engine.collect_metrics", return_value=MetricReading(95, 20, 30)),
        patch("serverwatch.engine.check_service", return_value=HealthReading("service", "demo.service", "unknown", "timeout")),
    ):
        engine.run_once()
        engine.run_once()
    open_incidents = [row for row in db.incidents() if row["status"] == "open"]
    assert {row["rule_key"] for row in open_incidents} == {"resource:cpu", "service:demo.service"}
    assert len(open_incidents) == 2
    db.close()


def test_engine_resolves_recovered_conditions(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "db.sqlite", test_mode=True, services=("demo.service",), endpoints=())
    db = Database(settings.db_path)
    engine = MonitorEngine(settings, db)
    with (
        patch("serverwatch.engine.collect_metrics", side_effect=[MetricReading(95, 20, 30), MetricReading(10, 20, 30)]),
        patch("serverwatch.engine.check_service", side_effect=[HealthReading("service", "demo.service", "unhealthy", "failed"), HealthReading("service", "demo.service", "healthy", "active")]),
    ):
        engine.run_once()
        engine.run_once()
    assert all(row["status"] == "resolved" for row in db.incidents())
    db.close()


def test_collector_failure_is_visible_and_resolves_after_recovery(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "db.sqlite", test_mode=True, services=(), endpoints=())
    db = Database(settings.db_path)
    engine = MonitorEngine(settings, db)
    with patch("serverwatch.engine.collect_metrics", side_effect=RuntimeError("collector fault")):
        with pytest.raises(RuntimeError):
            engine.run_once()
    assert db.incidents()[0]["rule_key"] == "collector:failed"
    assert db.incidents()[0]["status"] == "open"
    with patch("serverwatch.engine.collect_metrics", return_value=MetricReading(10, 20, 30)):
        engine.run_once()
    assert db.incidents()[0]["status"] == "resolved"
    assert db.rows("SELECT status FROM collector_runs ORDER BY id") == [{"status": "failed"}, {"status": "ok"}]
    db.close()
