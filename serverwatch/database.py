from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    def _create_schema(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS metric_samples (
          id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL,
          cpu_percent REAL NOT NULL, memory_percent REAL NOT NULL, disk_percent REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_observed ON metric_samples(observed_at);
        CREATE TABLE IF NOT EXISTS health_samples (
          id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL, kind TEXT NOT NULL,
          name TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('healthy','unhealthy','unknown')),
          detail TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_health_observed ON health_samples(observed_at);
        CREATE TABLE IF NOT EXISTS incidents (
          id INTEGER PRIMARY KEY, rule_key TEXT NOT NULL, title TEXT NOT NULL,
          condition TEXT NOT NULL, measured_value TEXT NOT NULL,
          opened_at TEXT NOT NULL, resolved_at TEXT, status TEXT NOT NULL CHECK(status IN ('open','resolved')),
          acknowledged_at TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_incident ON incidents(rule_key) WHERE status='open';
        CREATE TABLE IF NOT EXISTS notification_attempts (
          id INTEGER PRIMARY KEY, incident_id INTEGER, attempted_at TEXT NOT NULL,
          channel TEXT NOT NULL, attempt_number INTEGER NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('sent','failed','skipped')),
          detail TEXT NOT NULL,
          FOREIGN KEY(incident_id) REFERENCES incidents(id)
        );
        CREATE TABLE IF NOT EXISTS collector_runs (
          id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
          status TEXT NOT NULL CHECK(status IN ('running','ok','failed')), detail TEXT NOT NULL
        );
        """
        with self._lock, self._connection:
            self._connection.executescript(schema)

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock, self._connection:
            return self._connection.execute(sql, params)

    def rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._connection.execute(sql, params).fetchall()]

    def add_metric(self, cpu: float, memory: float, disk: float, observed_at: str | None = None) -> None:
        self.execute(
            "INSERT INTO metric_samples(observed_at,cpu_percent,memory_percent,disk_percent) VALUES(?,?,?,?)",
            (observed_at or utc_now(), cpu, memory, disk),
        )

    def add_health(self, kind: str, name: str, status: str, detail: str, observed_at: str | None = None) -> None:
        self.execute(
            "INSERT INTO health_samples(observed_at,kind,name,status,detail) VALUES(?,?,?,?,?)",
            (observed_at or utc_now(), kind, name, status, detail[:500]),
        )

    def start_run(self) -> int:
        return int(self.execute(
            "INSERT INTO collector_runs(started_at,status,detail) VALUES(?,'running','')", (utc_now(),)
        ).lastrowid)

    def finish_run(self, run_id: int, status: str, detail: str = "") -> None:
        self.execute(
            "UPDATE collector_runs SET completed_at=?,status=?,detail=? WHERE id=?",
            (utc_now(), status, detail[:1000], run_id),
        )

    def open_incident(self, rule_key: str, title: str, condition: str, measured: str) -> tuple[int, bool]:
        existing = self.rows("SELECT id FROM incidents WHERE rule_key=? AND status='open'", (rule_key,))
        if existing:
            return int(existing[0]["id"]), False
        incident_id = int(self.execute(
            "INSERT INTO incidents(rule_key,title,condition,measured_value,opened_at,status) VALUES(?,?,?,?,?,'open')",
            (rule_key, title, condition, measured, utc_now()),
        ).lastrowid)
        return incident_id, True

    def resolve_incident(self, rule_key: str) -> bool:
        cursor = self.execute(
            "UPDATE incidents SET status='resolved',resolved_at=? WHERE rule_key=? AND status='open'",
            (utc_now(), rule_key),
        )
        return cursor.rowcount > 0

    def latest_metric(self) -> dict[str, Any] | None:
        rows = self.rows("SELECT * FROM metric_samples ORDER BY observed_at DESC LIMIT 1")
        return rows[0] if rows else None

    def latest_health(self) -> list[dict[str, Any]]:
        return self.rows("""
          SELECT h.* FROM health_samples h JOIN (
            SELECT kind,name,MAX(id) AS max_id FROM health_samples GROUP BY kind,name
          ) x ON h.id=x.max_id ORDER BY h.kind,h.name
        """)

    def metrics_since(self, hours: int) -> list[dict[str, Any]]:
        since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        return self.rows(
            "SELECT observed_at,cpu_percent,memory_percent,disk_percent FROM metric_samples "
            "WHERE observed_at>=? ORDER BY observed_at", (since,)
        )

    def incidents(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.rows("SELECT * FROM incidents ORDER BY opened_at DESC LIMIT ?", (limit,))

    def notification_attempts(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.rows("SELECT * FROM notification_attempts ORDER BY attempted_at DESC LIMIT ?", (limit,))

    def record_notification(self, incident_id: int | None, attempt: int, status: str, detail: str) -> None:
        self.execute(
            "INSERT INTO notification_attempts(incident_id,attempted_at,channel,attempt_number,status,detail) "
            "VALUES(?,?,'smtp',?,?,?)",
            (incident_id, utc_now(), attempt, status, detail[:500]),
        )

    def acknowledge(self, incident_id: int) -> bool:
        cursor = self.execute(
            "UPDATE incidents SET acknowledged_at=? WHERE id=? AND acknowledged_at IS NULL",
            (utc_now(), incident_id),
        )
        return cursor.rowcount > 0

