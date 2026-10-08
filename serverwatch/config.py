from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("/var/lib/serverwatch/serverwatch.db")
    username: str = "admin"
    password_hash: str = ""
    interval_seconds: int = 60
    stale_after_seconds: int = 180
    cpu_threshold: float = 90.0
    memory_threshold: float = 90.0
    disk_threshold: float = 90.0
    notification_cooldown_seconds: int = 900
    services: tuple[str, ...] = ("bouncer.service", "tailscaled.service", "ssh.service")
    endpoints: tuple[str, ...] = ("http://127.0.0.1:8501/",)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_starttls: bool = True
    test_mode: bool = False
    root_path: str = "/serverwatch"

    @classmethod
    def from_env(cls) -> "Settings":
        def integer(name: str, default: int, minimum: int = 1) -> int:
            value = int(os.getenv(name, str(default)))
            if value < minimum:
                raise ValueError(f"{name} must be at least {minimum}")
            return value

        def number(name: str, default: float) -> float:
            value = float(os.getenv(name, str(default)))
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
            return value

        def string_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
            raw = os.getenv(name)
            if raw is None:
                return default
            value = json.loads(raw)
            if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
                raise ValueError(f"{name} must be a JSON array of non-empty strings")
            return tuple(value)

        return cls(
            db_path=Path(os.getenv("SERVERWATCH_DB_PATH", str(cls.db_path))),
            username=os.getenv("SERVERWATCH_USERNAME", cls.username),
            password_hash=os.getenv("SERVERWATCH_PASSWORD_HASH", ""),
            interval_seconds=integer("SERVERWATCH_INTERVAL_SECONDS", cls.interval_seconds),
            stale_after_seconds=integer("SERVERWATCH_STALE_AFTER_SECONDS", cls.stale_after_seconds),
            cpu_threshold=number("SERVERWATCH_CPU_THRESHOLD", cls.cpu_threshold),
            memory_threshold=number("SERVERWATCH_MEMORY_THRESHOLD", cls.memory_threshold),
            disk_threshold=number("SERVERWATCH_DISK_THRESHOLD", cls.disk_threshold),
            notification_cooldown_seconds=integer(
                "SERVERWATCH_NOTIFICATION_COOLDOWN_SECONDS", cls.notification_cooldown_seconds, 0
            ),
            services=string_list("SERVERWATCH_SERVICES", cls.services),
            endpoints=string_list("SERVERWATCH_ENDPOINTS", cls.endpoints),
            smtp_host=os.getenv("SERVERWATCH_SMTP_HOST", ""),
            smtp_port=integer("SERVERWATCH_SMTP_PORT", cls.smtp_port),
            smtp_username=os.getenv("SERVERWATCH_SMTP_USERNAME", ""),
            smtp_password=os.getenv("SERVERWATCH_SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SERVERWATCH_SMTP_FROM", ""),
            smtp_to=os.getenv("SERVERWATCH_SMTP_TO", ""),
            smtp_starttls=os.getenv("SERVERWATCH_SMTP_STARTTLS", "true").lower() == "true",
            test_mode=os.getenv("SERVERWATCH_TEST_MODE", "false").lower() == "true",
            root_path=os.getenv("SERVERWATCH_ROOT_PATH", cls.root_path),
        )

    @property
    def notifications_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from and self.smtp_to)

