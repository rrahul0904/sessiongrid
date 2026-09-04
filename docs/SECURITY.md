# Security Architecture

SessionGrid handles sensitive authenticated browser state, so runtime isolation and secret handling are first-class boundaries.

## Baseline controls

- TLS everywhere outside local development.
- Secrets referenced through a vault/KMS-backed store.
- Encrypt persistent profile state with tenant-scoped envelope encryption.
- Never write passwords, cookies, auth headers or browser storage to application logs.
- Separate control-plane service identity from runtime-worker identity.
- Use short-lived worker credentials.
- Apply organization/workspace/profile authorization on every request.
- Record privileged actions in append-only audit storage.
- Rate-limit session and input APIs.
- Apply retention policies to screenshots/recordings.

## Runtime sandbox

Production workers should be disposable and hardened:
- rootless container or VM
- no host Docker socket
- seccomp/AppArmor where available
- read-only base filesystem
- isolated writable profile mount
- restricted cloud metadata access
- explicit egress policy where required
- per-session resource limits

## Threat model highlights

### Cross-tenant profile disclosure
Mitigation: tenant id on every domain record, scoped queries, object-storage prefixes + IAM conditions, automated authorization tests.

### Malicious page attacks worker
Mitigation: disposable sandbox, patched Chromium, no host privileges, minimal worker credential scope.

### Insider accesses account state
Mitigation: state encryption, KMS policy, no raw-state UI, dual-control for exports, audit.

### Agent executes unintended side effect
Mitigation: allowlisted tools, typed action schema, policy evaluation, approval gate, budgets, idempotency keys.

### Stolen operator session
Mitigation: MFA/SSO, short sessions, device/IP policies for enterprise, sensitive-action reauth.

## Explicit product boundary

Security features must not be repurposed as anti-detection or ban-evasion features. SessionGrid isolates authorized customer workspaces; it does not promise or engineer platform-enforcement circumvention.
