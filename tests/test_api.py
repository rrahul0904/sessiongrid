import os
from pathlib import Path

TEST_DB = Path("test_sessiongrid.db")
TEST_DB.unlink(missing_ok=True)

os.environ.setdefault("SESSIONGRID_DATABASE_URL", "sqlite:///./test_sessiongrid.db")
os.environ.setdefault("SESSIONGRID_RUNTIME_DIR", "./test_runtime_data")
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
        assert all(p["organization_id"] == me.json()["organization"]["id"] for p in profiles.json())


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


def teardown_module():
    TEST_DB.unlink(missing_ok=True)
    import shutil
    shutil.rmtree("test_runtime_data", ignore_errors=True)
