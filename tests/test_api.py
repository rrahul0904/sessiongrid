import os
from pathlib import Path

os.environ.setdefault("SESSIONGRID_DATABASE_URL", "sqlite:///./test_sessiongrid.db")
os.environ.setdefault("SESSIONGRID_RUNTIME_DIR", "./test_runtime_data")

from fastapi.testclient import TestClient
from app.main import app


def test_health_and_seeded_profiles():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        profiles = client.get("/api/profiles")
        assert profiles.status_code == 200
        assert len(profiles.json()) >= 1


def test_profile_create_and_overview():
    with TestClient(app) as client:
        before = client.get("/api/overview").json()["profiles"]
        response = client.post(
            "/api/profiles",
            json={
                "name": "QA Workspace",
                "platform": "Web QA",
                "owner": "Tester",
                "locale": "en-US",
                "timezone": "America/New_York",
                "start_url": "https://example.com",
                "network_label": "Default egress",
            },
        )
        assert response.status_code == 201
        after = client.get("/api/overview").json()["profiles"]
        assert after == before + 1


def teardown_module():
    Path("test_sessiongrid.db").unlink(missing_ok=True)
    import shutil
    shutil.rmtree("test_runtime_data", ignore_errors=True)
