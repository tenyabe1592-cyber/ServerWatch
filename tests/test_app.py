from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasicCredentials

from serverwatch.auth import hash_password
from serverwatch.app import create_app
from serverwatch.config import Settings


def endpoint(app, path: str, method: str = "GET"):
    return next(route.endpoint for route in app.routes if route.path == path and method in route.methods)


def authentication_dependency(app, path: str = "/"):
    route = next(route for route in app.routes if route.path == path)
    return route.dependant.dependencies[0].call


def test_health_is_public_but_dashboard_has_required_auth(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "db.sqlite", password_hash=hash_password("a-long-test-password", iterations=1_000))
    app = create_app(settings, start_worker=False)
    assert endpoint(app, "/healthz")() == {"status": "ok"}
    require_auth = authentication_dependency(app)
    with pytest.raises(HTTPException) as error:
        require_auth(None)
    assert error.value.status_code == 401
    assert require_auth(HTTPBasicCredentials(username="admin", password="a-long-test-password")) == "admin"
    assert isinstance(endpoint(app, "/")(), FileResponse)
    app.state.db.close()


def test_status_distinguishes_stale_and_unknown(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "db.sqlite", test_mode=True, stale_after_seconds=60)
    app = create_app(settings, start_worker=False)
    old = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    app.state.db.add_metric(10, 20, 30, old)
    app.state.db.add_health("service", "demo", "unknown", "timeout", old)
    payload = endpoint(app, "/api/status")()
    assert payload["stale"] is True
    assert payload["health"][0]["status"] == "unknown"
    app.state.db.close()


def test_incident_api_reads_persisted_history(tmp_path: Path):
    settings = Settings(db_path=tmp_path / "db.sqlite", test_mode=True)
    app = create_app(settings, start_worker=False)
    app.state.db.open_incident("test", "Test", "condition", "value")
    assert endpoint(app, "/api/incidents")()[0]["title"] == "Test"
    app.state.db.close()

