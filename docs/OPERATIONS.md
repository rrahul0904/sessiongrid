# Operations Runbook

## Local health

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/overview
```

## Common local issues

### Chromium is missing
Run:
```bash
playwright install chromium
```

### Runtime cannot launch in a container
Use the provided Dockerfile, which installs Playwright Chromium dependencies. Production workers should run with a purpose-built hardened image and explicit sandbox policy.

### SQLite is locked
The MVP is single-process/local by design. Move to PostgreSQL before horizontal scaling.

### Session shows error
Inspect the safe `error` field on `/api/sessions`. Do not log or expose credential/session-state contents.

## Production alerts

Create alerts for:
- API 5xx rate
- session-start failure rate
- worker heartbeat loss
- queue age
- runtime saturation
- WebRTC connection failures
- object-store write failures
- PostgreSQL saturation/replication lag
- KMS/Vault errors
- workflow retries/dead letters
- abnormal tenant spend

## Recovery

Control-plane records remain authoritative. If a worker dies:
1. lease expires
2. orchestrator marks the allocation lost
3. recover from the most recent valid encrypted state snapshot
4. retry only if policy/idempotency rules allow
5. append an audit/recovery event

## Cost operations

Track per tenant:
- browser runtime seconds
- Android runtime seconds
- CPU/memory reservation
- egress bytes
- artifact storage
- WebRTC bandwidth
- AI tokens/provider spend

Set budget alerts before enabling autonomous or scheduled workloads.
