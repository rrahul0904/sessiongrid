# Roadmap

## Now — Foundation
- [x] public repository
- [x] product/architecture docs
- [x] runnable FastAPI MVP
- [x] profile inventory
- [x] local persistent Chromium runtime
- [x] session start/stop
- [x] screen grid
- [x] screenshot/input endpoints
- [x] audit events
- [x] Docker + tests + CI

## Next — Control plane
- [x] PostgreSQL + Alembic
- [x] organizations/workspaces/users
- [x] scoped API-key auth + RBAC foundation
- [ ] OIDC/SAML human authentication
- [ ] policy service
- [ ] encrypted secret references
- [x] usage ledger foundation
- [x] session-start idempotency
- [ ] cursor pagination across large inventories
- [ ] structured logs + OpenTelemetry

## Runtime scale
- [x] durable runtime task records
- [x] runtime orchestrator foundation
- [x] local worker registry + heartbeat metadata
- [x] runtime leases
- [x] organization-scoped start idempotency
- [x] artifact metadata + local ArtifactStore abstraction
- [x] explicit evidence capture + SHA-256
- [x] concurrency quotas
- [x] runtime-seconds usage ledger
- [ ] separate remote worker service
- [ ] authenticated task claiming
- [ ] active heartbeat/lease-renewal loop
- [x] expired-lease startup recovery
- [ ] encrypted profile-state snapshots
- [ ] S3-compatible object-store provider
- [ ] regional placement across remote worker pools
- [ ] WebRTC streaming
- [ ] control ownership/handoff

## Automation
- [ ] Temporal / distributed durable execution
- [x] workflow definitions + versioning
- [x] durable workflow runs + step runs
- [x] approval service
- [x] evidence/artifact requirement step
- [x] built-in evidence-review template
- [ ] policy-aware side effects
- [ ] runtime action executor steps
- [ ] QA/support/localization template library

## AI
- [ ] bounded agent runtime
- [ ] context/evidence bundle
- [ ] allowlisted tools
- [ ] human approval nodes
- [ ] provider abstraction
- [ ] cost/token budgets
- [ ] evaluation suite

## Android
- [ ] provider spike
- [ ] Anbox/Cuttlefish evaluation
- [ ] Android runtime contract
- [ ] touch/text/stream
- [ ] persistent encrypted state
- [ ] capacity + cost dashboards

## Enterprise
- [ ] SAML/SSO
- [ ] SCIM
- [ ] customer-managed keys
- [ ] private runtime pools
- [ ] retention controls
- [ ] exportable audit
- [ ] compliance readiness
