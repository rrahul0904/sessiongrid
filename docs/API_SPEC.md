# API Specification

## Current MVP routes

### Health
`GET /api/health`

### Overview
`GET /api/overview`

### Profiles
- `GET /api/profiles`
- `POST /api/profiles`

### Sessions
- `GET /api/sessions`
- `POST /api/profiles/{profile_id}/start`
- `POST /api/profiles/{profile_id}/stop`

### Screen/input
- `GET /api/profiles/{profile_id}/frame`
- `POST /api/profiles/{profile_id}/input/pointer`
- `POST /api/profiles/{profile_id}/input/text`

### Audit
`GET /api/audit`

## Production API conventions

- Prefix versioned APIs with `/api/v1`.
- Organization identity comes from authenticated principal, not arbitrary request body.
- Every mutation accepts/derives an idempotency key where duplication is dangerous.
- Use cursor pagination for inventory/audit lists.
- Return stable machine-readable failure codes.
- Use `202 Accepted` for long-running runtime/workflow operations.
- Expose operation resources so clients can poll or subscribe.
- Propagate request and trace ids.
- Never return raw credential/session-state blobs.

## Example production session request

```json
{
  "profile_id": "prf_123",
  "runtime_type": "browser",
  "region": "us-east",
  "max_runtime_seconds": 3600
}
```

Possible lifecycle:
`queued -> provisioning -> running -> stopping -> stopped`

Terminal error states include a typed `failure_code` and safe diagnostic message.
