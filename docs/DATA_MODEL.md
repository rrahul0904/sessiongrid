# Data Model

## Core entities

### Organization
Tenant boundary, billing owner and top-level security scope.

### User
Human identity authenticated through OIDC/SSO.

### Membership
Connects users to organizations with roles.

### Workspace
Client/team boundary inside an organization.

### Profile
Persistent authorized browser or Android workspace.

Suggested fields:
- id
- organization_id
- workspace_id
- name
- platform
- runtime_type
- owner_user_id
- locale
- timezone
- start_url
- network_policy_id
- state_key_ref
- status
- created_at / archived_at

### Session
One runtime allocation for one profile.

Suggested fields:
- id
- profile_id
- organization_id
- status
- provider
- worker_id
- lease_version
- started_at / stopped_at
- failure_code / failure_detail
- runtime_seconds
- egress_bytes
- cost_microunits

### AuditEvent
Append-only actor/action/resource event.

### Artifact
Screenshot, recording, state snapshot or workflow evidence reference.

### WorkflowDefinition / WorkflowRun / WorkflowStep
Durable automation domain.

### Approval
Records who approved/rejected a sensitive action and why.

### UsageEvent
Append-only metering event for runtime, storage, traffic and AI-provider spend.

## Relationships

```text
Organization
  +-- Membership -- User
  +-- Workspace
       +-- Profile
            +-- Session
                 +-- Artifact
                 +-- UsageEvent
            +-- WorkflowRun
                 +-- WorkflowStep
                 +-- Approval
  +-- AuditEvent
```

## Storage split

PostgreSQL owns relational/control state. Object storage owns large binary artifacts and encrypted state snapshots. High-volume telemetry may move to ClickHouse later; it must not become the source of truth for lifecycle state.
