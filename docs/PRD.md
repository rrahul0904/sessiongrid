# Product Requirements Document

## V0 / initial vertical slice

### Required
- Create/list profiles.
- Persist profile metadata.
- Start/stop an isolated Chromium workspace.
- Persist browser state per profile.
- Render active sessions in a grid.
- Capture screenshots.
- Forward basic pointer and text input.
- Show usage/health summary.
- Record operator audit events.
- Run locally and in Docker.
- Provide tests and CI.

### Not in V0
- production authentication
- distributed workers
- WebRTC
- Android
- billing
- workflow builder
- AI-agent execution

## Production control-plane requirements

### Organizations
- organization, workspace and client boundaries
- invite/disable members
- roles: owner, admin, manager, operator, reviewer, viewer, agent
- per-profile permission grants

### Profile lifecycle
- create/archive/restore
- labels and groups
- locale/timezone/runtime type
- secret references rather than plaintext credentials
- state encryption key reference
- runtime policy
- network policy reference

### Session lifecycle
- queued -> provisioning -> running -> stopping -> stopped
- failure class + retryability
- worker lease and heartbeat
- idle timeout
- max runtime
- concurrency quota
- cost attribution

### Audit/evidence
- append-only audit stream
- screenshots/recording artifact references
- actor can be user/service/agent
- approval decision and policy reason
- immutable timestamps

### Automation
- durable workflows
- retries/idempotency
- human approval nodes
- policy checks before execution
- evidence attachment
- cancellation and timeout

## Non-functional requirements

- API p95 under 300 ms for control-plane reads excluding runtime provisioning.
- 99.9% control-plane availability target after production hardening.
- Runtime starts should be idempotent.
- Worker failure must not corrupt profile state.
- No platform credential in application logs.
- Tenant isolation must hold across metadata, state and artifacts.
- All privileged actions must be auditable.

## Acceptance criteria for this repository

- `pytest -q` passes.
- App starts with `uvicorn app.main:app`.
- Four demo profiles seed into an empty DB.
- Profile creation changes overview count.
- Browser runtime has a persistent per-profile directory.
- Docker image contains Chromium installed by Playwright.
