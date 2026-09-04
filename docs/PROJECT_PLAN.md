# Project Plan

## Objective

Turn the validated concept into a production-grade SessionGrid platform without over-investing in Android virtualization before the browser/control-plane wedge proves demand.

## Workstreams

### A. Product
- operator interviews with agencies, brands, QA and community teams
- define top 3 paid workflows
- validate profile/concurrency pricing
- measure willingness to replace shared passwords/phones

### B. Control plane
- tenant model
- auth/RBAC
- profiles/policies
- audit/evidence
- billing/usage

### C. Runtime
- durable orchestration
- browser workers
- encrypted persistent state
- streaming/input
- Android provider later

### D. Automation/AI
- workflow engine
- human approvals
- bounded agent tools
- evidence/context intelligence
- evaluation and budget controls

### E. Platform
- Docker/Kubernetes
- observability
- CI/CD
- backups/recovery
- security/compliance

## Milestones

### M0 — runnable draft
Repository, docs, local browser runtime, dashboard, tests.

### M1 — team-ready alpha
Organizations, login, roles, PostgreSQL, profile inventory, audit, deployment.

### M2 — distributed browser beta
Worker pool, durable sessions, encrypted state, WebRTC, usage/cost metering.

### M3 — workflow beta
Temporal workflows, approvals, evidence, operator queue, policy service.

### M4 — AI-assisted operations
Bounded agents for QA, localization and support triage with complete traceability.

### M5 — Android pilot
Android provider integrated behind the common runtime contract for selected customers.

### M6 — enterprise
SSO/SCIM, private pools, retention, CMK, compliance controls.

## Delivery rules

- Never trade tenant isolation for development speed.
- Do not add stealth/detection-evasion features.
- Every distributed state transition must be idempotent/recoverable.
- Every high-cost service must emit usage/cost telemetry.
- Every AI side effect must be policy-evaluated and auditable.
