# End-to-End Implementation Plan

## Phase 0 — repository foundation (this commit)

Deliver:
- product and architecture docs
- runnable FastAPI MVP
- profile/session/audit schema
- local persistent Chromium runtime
- screen grid
- Docker
- tests + CI

Exit gate:
- repository boots locally
- API health succeeds
- profile CRUD slice works
- session start/stop path exists
- CI runs tests

## Phase 1 — production control plane

Build:
- PostgreSQL + Alembic
- organizations, users, memberships, workspaces
- RBAC + policy service
- OIDC auth
- encrypted secret references
- usage ledger
- rate limits and concurrency quotas
- structured audit events

Exit gate:
- tenant-isolation tests
- authorization matrix tests
- zero plaintext secret logging
- migration/rollback path validated

## Phase 2 — distributed browser runtime

Split the local RuntimeManager into:
- runtime orchestrator
- durable session queue
- worker registry/capability inventory
- worker lease/heartbeat
- browser worker image
- encrypted profile-state snapshots
- artifact service

Add:
- start idempotency
- retry taxonomy
- cancellation
- idle/max-runtime policy
- regional placement
- capacity and cost reporting

Exit gate:
- kill worker during active run and recover safely
- no duplicate active session after retry
- 100+ synthetic concurrent-session test target

## Phase 3 — production streaming

Replace screenshot polling with:
- WebRTC signaling
- low-latency video
- pointer/keyboard/touch data channel
- reconnect semantics
- viewer/operator ownership
- control handoff

Keep screenshots as evidence capture.

## Phase 4 — workflows and approvals

Introduce Temporal workflows:
- triggers
- runtime acquisition
- observation/read steps
- agent draft steps
- approval nodes
- execution steps
- evidence capture
- policy checks
- timeouts/retries/cancel

Ship workflow templates for QA, support triage, link verification and localization review.

## Phase 5 — Android runtime

Implement AndroidRuntimeProvider behind the common runtime contract. Begin with a managed Anbox/Cuttlefish deployment rather than custom virtualization.

Capabilities:
- persistent Android workspace
- APK/app lifecycle where legally/contractually permitted
- visual stream
- touch/text input
- screenshot/recording
- state reset
- capacity and runtime-minute metering

## Phase 6 — AI agents

Agent architecture:
- planner restricted to approved tools
- policy engine before side effects
- evidence/context bundle
- human approval where required
- bounded token/time/cost budgets
- complete run trace

Do not build stealth social bots or platform-enforcement circumvention.

## Phase 7 — enterprise

- SSO/SAML
- SCIM
- private runtime pools
- customer-managed keys
- IP/region policies
- retention controls
- exportable audit
- compliance evidence
- SLA dashboards

## Engineering quality gates

Every phase must add:
- unit tests
- integration tests
- threat-model delta
- load/failure tests where relevant
- cost model update
- operator runbook
- rollback procedure
