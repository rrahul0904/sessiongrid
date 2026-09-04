# Technical Architecture

## Target topology

```text
                         +----------------------+
Browser / API ---------->| Edge / API Gateway   |
                         +----------+-----------+
                                    |
                         +----------v-----------+
                         | Control Plane        |
                         | auth/org/profile     |
                         | policy/audit/billing |
                         +----------+-----------+
                                    |
                    +---------------+----------------+
                    |                                |
          +---------v----------+           +---------v----------+
          | Runtime            |           | Workflow           |
          | Orchestrator       |           | Orchestrator       |
          | placement/leases   |           | durable jobs       |
          +---------+----------+           +---------+----------+
                    |                                |
          +---------+----------+                     |
          |                    |                     |
 +--------v---------+ +--------v---------+           |
 | Browser workers  | | Android workers  |<----------+
 | Playwright       | | Anbox/Cuttlefish |
 | Chromium         | | future           |
 +--------+---------+ +--------+---------+
          |                    |
          +---------+----------+
                    |
          +---------v----------+
          | Streaming Gateway |
          | WebRTC + input     |
          +--------------------+

PostgreSQL      -> control metadata
Object storage  -> screenshots/recordings/encrypted state artifacts
Redis           -> ephemeral cache/presence only
Temporal/queue  -> durable orchestration
OTel backend    -> traces/metrics/logs
ClickHouse      -> optional high-volume usage/cost analytics
KMS/Vault       -> secrets and envelope-encryption keys
```

## MVP topology

The initial draft intentionally uses one FastAPI process:

```text
Dashboard -> FastAPI -> SQLAlchemy -> SQLite
                  |
                  +-> RuntimeManager -> Playwright -> Chromium
```

This is a product-validation architecture, not the final scaling boundary.

## Runtime provider contract

Every runtime provider should implement equivalent operations:

- provision(profile, policy)
- start(session)
- inspect(session)
- stream(session)
- send_input(session, event)
- capture(session)
- stop(session)
- persist_state(session)
- destroy(session)

This lets browser, Android and private-device providers coexist.

## State model

Control-plane state is authoritative in PostgreSQL. Runtime workers are disposable. Persistent profile state is encrypted and stored separately from worker lifecycle. A worker receives only short-lived access to the state and secrets required for the assigned session.

## Scaling

Scale control-plane APIs horizontally behind a load balancer. Runtime workers scale based on concurrency and capacity, not request volume. Session placement uses worker capability, tenant policy, region and current load. Durable leases/heartbeats allow recovery when a worker disappears.

## Failure semantics

- start requests are idempotent per profile/session key
- worker leases expire
- session state transitions use optimistic concurrency
- retries distinguish transient vs terminal failures
- artifact writes use unique keys and checksums
- state snapshots are versioned before replacement

## Observability

Every user action gets a request/trace id. Propagate organization, session, worker and workflow ids through traces without leaking secrets. Meter runtime-minutes, egress bytes, storage and agent/provider cost per organization.
