# SessionGrid

SessionGrid is a policy-aware multi-session social operations control plane for teams that need to manage many authorized browser and, later, Android workspaces from one dashboard.

> **Scope:** secure isolation, remote workspaces, team access, auditability, human approvals, QA, support, localization, and policy-aware automation. SessionGrid deliberately does not implement fingerprint spoofing, CAPTCHA bypass, ban evasion, mass account creation, engagement manipulation, or stealth automation.

## Current MVP

The initial repository contains a runnable FastAPI vertical slice with:

- profile inventory and profile creation
- isolated persistent Playwright/Chromium sessions
- start/stop session lifecycle
- multi-session screen grid
- screenshot capture and polling
- basic pointer/text input forwarding
- audit events
- usage/health overview
- Docker packaging
- automated tests and CI
- product, architecture, security, deployment, Android-runtime, automation, AI-agent, and implementation docs

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Architecture direction

```text
Web Dashboard / API
        |
        v
SessionGrid Control Plane
(auth, orgs, profiles, policy, audit, billing)
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

The MVP intentionally collapses the control plane and browser worker into one process so the product is easy to run and validate. Production phases split those responsibilities into independently scalable services.

## Repository map

```text
app/                 runnable control-plane + browser-runtime MVP
docs/                product, architecture, implementation and operations specs
tests/               API tests
.github/workflows/   CI
Dockerfile           local/container packaging
docker-compose.yml   local deployment
```

## Delivery phases

1. **MVP:** browser profiles, sessions, grid, screenshots, audit
2. **Production control plane:** PostgreSQL, auth, orgs, RBAC, billing, durable jobs
3. **Distributed runtime:** worker pools, leases, WebRTC, observability, encrypted state
4. **Android runtime:** Anbox Cloud/Cuttlefish provider behind the same runtime contract
5. **Policy-aware automation:** workflows, approvals, evidence, agent execution
6. **Enterprise:** SSO/SCIM, private runtime pools, compliance controls, cost attribution

See `docs/IMPLEMENTATION_PLAN.md` and `docs/ARCHITECTURE.md`.

## License

MIT
