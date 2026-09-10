# SessionGrid

SessionGrid is a policy-aware multi-session social operations control plane for teams that manage authorized browser and, later, Android workspaces from one dashboard.

> **Scope:** secure isolation, remote workspaces, team access, auditability, human approvals, QA, support, localization, and policy-aware automation. SessionGrid deliberately does not implement fingerprint spoofing, CAPTCHA bypass, ban evasion, mass account creation, engagement manipulation, or stealth automation.

## Current implementation — Phase 2 runtime-orchestration foundation

The repository now contains a runnable browser MVP plus the first multi-tenant control-plane foundation:

- durable runtime task records, worker assignment and leases
- idempotent session starts via `Idempotency-Key`
- explicit screenshot evidence capture with SHA-256
- local ArtifactStore abstraction and tenant-scoped artifact APIs
- runtime worker/task/lease operator APIs
- organizations and workspaces
- users and organization memberships
- role hierarchy: owner/admin/manager/operator/reviewer/viewer
- organization-scoped API keys stored only as SHA-256 digests
- tenant-scoped profile/session/audit APIs
- organization concurrency limits
- append-only usage-event foundation
- PostgreSQL-compatible SQLAlchemy models
- Alembic baseline migration
- PostgreSQL Docker Compose environment
- profile inventory and creation
- isolated persistent Playwright/Chromium sessions
- session start/stop lifecycle
- multi-session screen grid
- screenshot polling and basic pointer/text input
- Docker packaging
- migration/API tests and CI

This is **not yet the final production platform**. The lifecycle is now durable, but execution still happens in the API process. A separate authenticated worker service, lease renewal/recovery, encrypted remote profile-state storage, WebRTC streaming, durable workflow execution, AI agents and Android workers remain later phases.

## Quick start — lightweight SQLite

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

Local development uses a seeded admin principal and auto-creates the SQLite schema.

## Quick start — PostgreSQL + migrations

```bash
cp .env.example .env
docker compose up --build
```

Compose starts PostgreSQL, runs `alembic upgrade head`, then launches SessionGrid at `http://localhost:8000`.

## Authentication

Local development defaults to:

```text
SESSIONGRID_AUTH_REQUIRED=false
```

For a shared environment, set a high-entropy bootstrap key and require authentication:

```text
SESSIONGRID_AUTH_REQUIRED=true
SESSIONGRID_BOOTSTRAP_API_KEY=<high-entropy-secret>
```

Then send:

```text
X-SessionGrid-API-Key: <secret>
```

API keys created through `POST /api/v1/api-keys` are returned once; only their SHA-256 digest is persisted. This is an interim service/API authentication mechanism. OIDC/SAML remains the production human-auth direction.

## Tenant context

A principal is always scoped to one organization. In local development, a user who belongs to multiple organizations can select one with:

```text
X-SessionGrid-Organization-ID: <organization-id>
```

A scoped API key cannot switch to another organization.

## Useful APIs

```text
GET  /api/health
GET  /api/v1/me
GET  /api/v1/organizations
POST /api/v1/organizations
GET  /api/v1/workspaces
POST /api/v1/workspaces
GET  /api/v1/members
POST /api/v1/members
POST /api/v1/api-keys
GET  /api/v1/usage
GET  /api/v1/runtime/workers
GET  /api/v1/runtime/tasks
GET  /api/v1/runtime/leases
GET  /api/v1/artifacts
GET  /api/v1/artifacts/{id}/content

GET  /api/profiles
POST /api/profiles
GET  /api/sessions
POST /api/profiles/{id}/start
POST /api/profiles/{id}/stop
GET  /api/profiles/{id}/frame
POST /api/profiles/{id}/capture
GET  /api/audit
```

Interactive API docs are available at `/docs`.

## Architecture direction

```text
Web Dashboard / API
        |
        v
SessionGrid Control Plane
(orgs, auth, RBAC, profiles, policy, audit, usage)
        |
        v
Runtime Orchestrator
        |
  +-----+------------------+
  |                        |
Browser Workers        Android Workers
Playwright/Chromium    Anbox/Cuttlefish (future)
  |                        |
  +------------+-----------+
               |
        Streaming Gateway
             WebRTC
```

The current browser executor is still in-process, but lifecycle intent is persisted as runtime tasks and leases. The next wave extracts execution into an authenticated worker service and adds active lease renewal, stale-worker recovery, encrypted state snapshots and WebRTC.

## Repository map

```text
app/                  control plane + local runtime MVP
alembic/              database migrations
docs/                 product, architecture, implementation and operations specs
tests/                tenant/API tests
.github/workflows/    CI + migration round-trip
Dockerfile            application image
docker-compose.yml    PostgreSQL local stack
```

## Next engineering wave

1. separate authenticated runtime worker service
2. task claiming, heartbeat renewal and expired-lease recovery
3. encrypted profile-state snapshots + S3-compatible ArtifactStore
4. structured telemetry and richer cost attribution
5. WebRTC streaming and control ownership
6. Temporal workflows and approval service
7. bounded evidence-aware AI agents
8. Android runtime provider
9. enterprise OIDC/SAML/SCIM and private pools

See `docs/RUNTIME_ORCHESTRATION.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/ARCHITECTURE.md`, and `docs/SECURITY.md`.

## License

MIT
