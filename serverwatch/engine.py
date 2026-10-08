from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from .config import Settings
from .database import Database
from .monitor import check_endpoint, check_service, collect_metrics
from .notifications import send_notification

LOGGER = logging.getLogger(__name__)


class MonitorEngine:
    def __init__(self, settings: Settings, db: Database):
        self.settings = settings
        self.db = db
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="serverwatch-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                LOGGER.exception("collector run failed")
            self._stop.wait(self.settings.interval_seconds)

    def _alert(self, rule_key: str, title: str, condition: str, measured: str, active: bool) -> None:
        if active:
            incident_id, created = self.db.open_incident(rule_key, title, condition, measured)
            if created:
                send_notification(
                    self.settings, self.db, incident_id, title,
                    f"{title}\nCondition: {condition}\nMeasured: {measured}\nOpened: {datetime.now(UTC).isoformat()}",
                )
        else:
            self.db.resolve_incident(rule_key)

    def run_once(self) -> None:
        run_id = self.db.start_run()
        try:
            previous = self.db.latest_metric()
            if previous:
                age = (datetime.now(UTC) - datetime.fromisoformat(previous["observed_at"])).total_seconds()
                self._alert(
                    "collector:stale", "Metric collection was stale",
                    f"sample age > {self.settings.stale_after_seconds}s", f"{age:.0f}s",
                    age > self.settings.stale_after_seconds,
                )
            metric = collect_metrics()
            self.db.add_metric(metric.cpu_percent, metric.memory_percent, metric.disk_percent)
            if not previous:
                self.db.resolve_incident("collector:stale")
            for name, value, threshold in (
                ("cpu", metric.cpu_percent, self.settings.cpu_threshold),
                ("memory", metric.memory_percent, self.settings.memory_threshold),
                ("disk", metric.disk_percent, self.settings.disk_threshold),
            ):
                self._alert(
                    f"resource:{name}", f"High {name} utilization", f">= {threshold:.1f}%",
                    f"{value:.1f}%", value >= threshold,
                )

            readings = [check_service(name) for name in self.settings.services]
            readings.extend(check_endpoint(url) for url in self.settings.endpoints)
            for reading in readings:
                self.db.add_health(reading.kind, reading.name, reading.status, reading.detail)
                self._alert(
                    f"{reading.kind}:{reading.name}", f"{reading.kind.title()} unhealthy: {reading.name}",
                    "status != healthy", f"{reading.status}: {reading.detail}", reading.status != "healthy",
                )
            self.db.resolve_incident("collector:stale")
            self.db.resolve_incident("collector:failed")
            self.db.finish_run(run_id, "ok")
        except Exception as exc:
            self.db.finish_run(run_id, "failed", f"{type(exc).__name__}: {exc}")
            self._alert("collector:failed", "Metric collection failed", "collector run must complete", type(exc).__name__, True)
            raise
