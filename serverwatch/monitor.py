from __future__ import annotations

import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class MetricReading:
    cpu_percent: float
    memory_percent: float
    disk_percent: float


@dataclass(frozen=True)
class HealthReading:
    kind: str
    name: str
    status: str
    detail: str


def collect_metrics() -> MetricReading:
    return MetricReading(
        cpu_percent=round(psutil.cpu_percent(interval=0.1), 1),
        memory_percent=round(psutil.virtual_memory().percent, 1),
        disk_percent=round(psutil.disk_usage("/").percent, 1),
    )


def check_service(name: str) -> HealthReading:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", name], capture_output=True, text=True, timeout=5, check=False
        )
        state = result.stdout.strip() or result.stderr.strip() or f"exit {result.returncode}"
        if result.returncode == 0 and state == "active":
            status = "healthy"
        elif state in {"inactive", "failed", "deactivating"}:
            status = "unhealthy"
        else:
            status = "unknown"
        return HealthReading("service", name, status, state)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return HealthReading("service", name, "unknown", type(exc).__name__)


def check_endpoint(url: str) -> HealthReading:
    try:
        request = urllib.request.Request(url, method="GET", headers={"User-Agent": "ServerWatch/1.0"})
        with urllib.request.urlopen(request, timeout=5) as response:
            code = response.status
        status = "healthy" if 200 <= code < 400 else "unhealthy"
        return HealthReading("endpoint", url, status, f"HTTP {code}")
    except urllib.error.HTTPError as exc:
        return HealthReading("endpoint", url, "unhealthy", f"HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HealthReading("endpoint", url, "unknown", type(exc).__name__)

