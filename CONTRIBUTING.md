# Contributing

1. Create a feature branch from `main`.
2. Keep changes aligned with the authorized-operations product boundary.
3. Add or update tests for behavior changes.
4. Update architecture/security docs when boundaries change.
5. Run `pytest -q` before opening a pull request.

## Product boundary

Do not contribute fingerprint spoofing, CAPTCHA bypass, ban-evasion, bulk account creation, engagement manipulation or stealth automation.

## Commit style

Prefer small conventional-style commits such as:
- `feat: add worker lease model`
- `fix: make session start idempotent`
- `docs: document runtime threat model`
