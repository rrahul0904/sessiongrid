# Runtime Orchestration

## What this phase implements

SessionGrid now persists the intent and assignment around browser execution instead of treating an in-process Playwright launch as the entire session model.

A session start produces durable control-plane records:

```text
Profile
  -> BrowserSession(status=queued)
  -> RuntimeTask(type=start,status=queued)
  -> RuntimeWorker assignment
  -> RuntimeLease(status=active)
  -> BrowserSession(status=provisioning)
  -> local executor launches Playwright
  -> RuntimeTask(status=succeeded)
  -> BrowserSession(status=running)
```

A stop operation creates a separate durable stop task and releases the lease after runtime shutdown.

## Current local executor

The executor is still in the FastAPI process. This is intentional for the current repository phase: it lets us validate lifecycle semantics, idempotency, evidence capture and operator UX before splitting compute across services.

The local worker is registered as a real `runtime_workers` record with:

- stable worker key
- region
- status
- capacity
- capability declaration
- heartbeat timestamp

The next split can therefore replace the local call with remote claiming/heartbeat protocols without changing public session semantics.

## Idempotency

`POST /api/profiles/{profile_id}/start` accepts:

```text
Idempotency-Key: <caller-generated-key>
```

The stored key is namespaced by organization. Replaying the same key for that organization returns the original BrowserSession instead of launching another runtime.

Even without a key, an already active session for the same profile is returned rather than duplicated.

## Leases

A runtime lease binds:

- organization
- profile
- session
- worker
- acquired time
- expiration time
- release time/status

The current local executor creates/releases these leases. The next distributed-worker phase adds active lease renewal, expiration recovery and remote worker claiming.

## Durable tasks

Runtime tasks capture start/stop work and retain:

- task type
- lifecycle state
- attempt count
- max attempts
- available time
- lock owner/time
- error details
- created/updated timestamps

This is the foundation for a database-backed claim loop or a durable workflow/queue system.

## Evidence artifacts

Explicit evidence capture is separate from low-value screen polling.

`POST /api/profiles/{profile_id}/capture`:

1. captures the active screen
2. writes it through the ArtifactStore abstraction
3. computes SHA-256
4. persists artifact metadata
5. appends an audit event

The local provider writes atomically to the filesystem. Production should implement the same interface with S3-compatible object storage, bucket encryption, retention and tenant-scoped IAM.

## Operator APIs

```text
GET /api/v1/runtime/workers
GET /api/v1/runtime/tasks
GET /api/v1/runtime/leases
GET /api/v1/artifacts
GET /api/v1/artifacts/{id}/content
POST /api/profiles/{id}/capture
```

Runtime infrastructure inventory is manager-or-higher; evidence capture is reviewer-or-higher.

## Next runtime work

1. move executor into a separate worker process
2. worker registration credentials
3. task claim endpoint/protocol
4. heartbeat + lease renewal loop
5. stale-worker detection
6. expired-lease recovery
7. retry/backoff semantics
8. encrypted profile-state snapshot provider
9. S3-compatible ArtifactStore
10. WebRTC streaming gateway
11. control ownership and reconnect semantics
12. load/failure testing at 100+ synthetic sessions
