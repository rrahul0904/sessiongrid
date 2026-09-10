import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

TEST_DB = Path("test_sessiongrid.db")
TEST_DB.unlink(missing_ok=True)
shutil.rmtree("test_runtime_data", ignore_errors=True)
shutil.rmtree("test_artifacts", ignore_errors=True)

os.environ.setdefault("SESSIONGRID_DATABASE_URL", "sqlite:///./test_sessiongrid.db")
os.environ.setdefault("SESSIONGRID_RUNTIME_DIR", "./test_runtime_data")
os.environ.setdefault("SESSIONGRID_ARTIFACT_DIR", "./test_artifacts")
os.environ.setdefault("SESSIONGRID_AUTH_REQUIRED", "false")
os.environ.setdefault("SESSIONGRID_AUTO_CREATE_SCHEMA", "true")

from fastapi.testclient import TestClient
from app.main import app


def test_health_seed_and_principal():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["version"] == "0.2.0"

        me = client.get("/api/v1/me")
        assert me.status_code == 200
        assert me.json()["role"] == "owner"
        assert me.json()["organization"]["slug"] == "sessiongrid-demo"

        profiles = client.get("/api/profiles")
        assert profiles.status_code == 200
        assert len(profiles.json()) >= 1
        assert all(
            p["organization_id"] == me.json()["organization"]["id"]
            for p in profiles.json()
        )


def test_profile_create_and_overview_are_tenant_scoped():
    with TestClient(app) as client:
        default_profiles = client.get("/api/profiles").json()
        default_names = {p["name"] for p in default_profiles}

        org_response = client.post(
            "/api/v1/organizations",
            json={"name": "Acme QA", "slug": "acme-qa"},
        )
        assert org_response.status_code == 201
        org_id = org_response.json()["id"]
        org_headers = {"X-SessionGrid-Organization-ID": str(org_id)}

        workspaces = client.get("/api/v1/workspaces", headers=org_headers)
        assert workspaces.status_code == 200
        assert len(workspaces.json()) == 1

        created = client.post(
            "/api/profiles",
            headers=org_headers,
            json={
                "name": "Acme Isolated Profile",
                "platform": "Web QA",
                "owner": "Tester",
                "locale": "en-US",
                "timezone": "America/New_York",
                "start_url": "https://example.com",
                "network_label": "Default egress",
            },
        )
        assert created.status_code == 201
        assert created.json()["organization_id"] == org_id

        acme_profiles = client.get("/api/profiles", headers=org_headers).json()
        assert {p["name"] for p in acme_profiles} == {"Acme Isolated Profile"}

        default_after = client.get("/api/profiles").json()
        assert {p["name"] for p in default_after} == default_names


def test_api_key_is_scoped_to_organization():
    with TestClient(app) as client:
        org_response = client.post(
            "/api/v1/organizations",
            json={"name": "Key Scope", "slug": "key-scope"},
        )
        assert org_response.status_code == 201
        org_id = org_response.json()["id"]
        org_headers = {"X-SessionGrid-Organization-ID": str(org_id)}

        key_response = client.post(
            "/api/v1/api-keys",
            headers=org_headers,
            json={"name": "integration-test"},
        )
        assert key_response.status_code == 201
        raw_key = key_response.json()["api_key"]
        assert raw_key.startswith("sg_")

        authenticated = client.get(
            "/api/v1/me",
            headers={"X-SessionGrid-API-Key": raw_key},
        )
        assert authenticated.status_code == 200
        assert authenticated.json()["organization"]["id"] == org_id

        wrong_scope = client.get(
            "/api/v1/me",
            headers={
                "X-SessionGrid-API-Key": raw_key,
                "X-SessionGrid-Organization-ID": "1",
            },
        )
        if org_id != 1:
            assert wrong_scope.status_code == 403


def test_member_and_workspace_management():
    with TestClient(app) as client:
        workspace = client.post(
            "/api/v1/workspaces",
            json={"name": "Localization", "slug": "localization"},
        )
        assert workspace.status_code == 201

        member = client.post(
            "/api/v1/members",
            json={
                "email": "reviewer@example.com",
                "display_name": "Review User",
                "role": "reviewer",
            },
        )
        assert member.status_code == 201
        assert member.json()["role"] == "reviewer"

        members = client.get("/api/v1/members")
        assert members.status_code == 200
        assert any(m["email"] == "reviewer@example.com" for m in members.json())


def test_runtime_orchestration_idempotency_leases_and_artifacts():
    with TestClient(app) as client:
        profile = client.get("/api/profiles").json()[0]
        profile_id = profile["id"]

        fake_page = SimpleNamespace(
            url="https://example.com/",
            title=AsyncMock(return_value="Example Domain"),
        )
        fake_runtime = SimpleNamespace(page=fake_page)

        with (
            patch(
                "app.main.runtime_manager.launch",
                new=AsyncMock(return_value=fake_runtime),
            ) as launch_mock,
            patch(
                "app.main.runtime_manager.stop",
                new=AsyncMock(return_value=None),
            ) as stop_mock,
            patch(
                "app.main.runtime_manager.screenshot",
                new=AsyncMock(return_value=b"fake-jpeg-evidence"),
            ),
        ):
            headers = {"Idempotency-Key": "runtime-test-001"}
            first = client.post(
                f"/api/profiles/{profile_id}/start",
                headers=headers,
            )
            assert first.status_code == 200
            assert first.json()["status"] == "running"
            assert first.json()["worker_id"] == "local-worker"

            second = client.post(
                f"/api/profiles/{profile_id}/start",
                headers=headers,
            )
            assert second.status_code == 200
            assert second.json()["id"] == first.json()["id"]
            assert launch_mock.await_count == 1

            workers = client.get("/api/v1/runtime/workers")
            assert workers.status_code == 200
            assert any(w["worker_key"] == "local-worker" for w in workers.json())

            tasks = client.get("/api/v1/runtime/tasks")
            assert tasks.status_code == 200
            start_tasks = [
                t for t in tasks.json()
                if t["session_id"] == first.json()["id"] and t["task_type"] == "start"
            ]
            assert len(start_tasks) == 1
            assert start_tasks[0]["status"] == "succeeded"
            assert start_tasks[0]["attempt_count"] == 1

            leases = client.get("/api/v1/runtime/leases")
            assert leases.status_code == 200
            session_leases = [
                item for item in leases.json()
                if item["session_id"] == first.json()["id"]
            ]
            assert len(session_leases) == 1
            assert session_leases[0]["status"] == "active"

            capture = client.post(f"/api/profiles/{profile_id}/capture")
            assert capture.status_code == 201
            artifact_id = capture.json()["id"]
            assert capture.json()["sha256"]
            assert capture.json()["size_bytes"] == len(b"fake-jpeg-evidence")

            artifact_content = client.get(
                f"/api/v1/artifacts/{artifact_id}/content"
            )
            assert artifact_content.status_code == 200
            assert artifact_content.content == b"fake-jpeg-evidence"
            assert artifact_content.headers["x-content-sha256"] == capture.json()["sha256"]

            stopped = client.post(f"/api/profiles/{profile_id}/stop")
            assert stopped.status_code == 200
            assert stopped.json()["status"] == "stopped"
            assert stop_mock.await_count == 1

            leases_after = client.get("/api/v1/runtime/leases").json()
            released = [
                item for item in leases_after
                if item["session_id"] == first.json()["id"]
            ]
            assert released[0]["status"] == "released"

            tasks_after = client.get("/api/v1/runtime/tasks").json()
            stop_tasks = [
                t for t in tasks_after
                if t["session_id"] == first.json()["id"] and t["task_type"] == "stop"
            ]
            assert len(stop_tasks) == 1
            assert stop_tasks[0]["status"] == "succeeded"

            usage = client.get("/api/v1/usage")
            assert usage.status_code == 200
            metrics = {row["metric"] for row in usage.json()}
            assert "session_start" in metrics
            assert "runtime_seconds" in metrics


def teardown_module():
    TEST_DB.unlink(missing_ok=True)
    shutil.rmtree("test_runtime_data", ignore_errors=True)
    shutil.rmtree("test_artifacts", ignore_errors=True)
