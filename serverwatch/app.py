from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.resources import files

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .auth import verify_password
from .config import Settings
from .database import Database
from .engine import MonitorEngine
from .notifications import send_notification

security = HTTPBasic(auto_error=False)


def create_app(settings: Settings | None = None, *, start_worker: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    db = Database(settings.db_path)
    engine = MonitorEngine(settings, db)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_worker:
            engine.start()
        yield
        engine.stop()
        db.close()

    app = FastAPI(
        title="ServerWatch", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None,
        root_path=settings.root_path, lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = db
    app.state.engine = engine

    def require_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> str:
        if settings.test_mode and not settings.password_hash:
            return "test"
        if not settings.password_hash:
            raise HTTPException(status_code=503, detail="authentication is not configured")
        valid = bool(
            credentials
            and secrets.compare_digest(credentials.username, settings.username)
            and verify_password(credentials.password, settings.password_hash)
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials",
                headers={"WWW-Authenticate": "Basic realm=ServerWatch"},
            )
        return credentials.username

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:"
        return response

    static = files("serverwatch").joinpath("static")

    @app.get("/", dependencies=[Depends(require_auth)], include_in_schema=False)
    def dashboard():
        return FileResponse(static.joinpath("index.html"))

    @app.get("/static/{name}", dependencies=[Depends(require_auth)], include_in_schema=False)
    def assets(name: str):
        if name not in {"app.js", "style.css"}:
            raise HTTPException(404)
        return FileResponse(static.joinpath(name))

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    @app.get("/api/status", dependencies=[Depends(require_auth)])
    def api_status():
        latest = db.latest_metric()
        stale = True
        if latest:
            age = (datetime.now(UTC) - datetime.fromisoformat(latest["observed_at"])).total_seconds()
            stale = age > settings.stale_after_seconds
        return {
            "metric": latest,
            "stale": stale,
            "health": db.latest_health(),
            "notifications_configured": settings.notifications_configured,
            "thresholds": {"cpu": settings.cpu_threshold, "memory": settings.memory_threshold, "disk": settings.disk_threshold},
        }

    @app.get("/api/metrics", dependencies=[Depends(require_auth)])
    def api_metrics(hours: int = 24):
        if not 1 <= hours <= 168:
            raise HTTPException(400, "hours must be between 1 and 168")
        return db.metrics_since(hours)

    @app.get("/api/incidents", dependencies=[Depends(require_auth)])
    def api_incidents():
        return db.incidents()

    @app.post("/api/incidents/{incident_id}/acknowledge", dependencies=[Depends(require_auth)])
    def acknowledge(incident_id: int):
        if not db.acknowledge(incident_id):
            raise HTTPException(404, "incident not found or already acknowledged")
        return {"acknowledged": True}

    @app.get("/api/notifications", dependencies=[Depends(require_auth)])
    def notification_history():
        return db.notification_attempts()

    @app.post("/api/notifications/test", dependencies=[Depends(require_auth)])
    def test_notification():
        sent = send_notification(settings, db, None, "Test notification", "ServerWatch notification test.")
        return JSONResponse({"sent": sent}, status_code=200 if sent else 503)

    return app
