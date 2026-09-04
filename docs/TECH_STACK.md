# Technology Stack

## Initial repository

| Layer | Choice | Why |
|---|---|---|
| Web/control plane | FastAPI + Python | fast vertical slice, async-friendly runtime control |
| Persistence | SQLAlchemy + SQLite | zero-friction local MVP, easy PostgreSQL migration |
| Browser runtime | Playwright + Chromium | mature automation/control API and persistent contexts |
| UI | server-served HTML/CSS/JS | minimal deployment surface for first draft |
| Tests | Pytest + TestClient | fast API validation |
| Packaging | Docker / Compose | portable local demo |
| CI | GitHub Actions | repository-native quality gate |

## Production evolution

| Layer | Recommended |
|---|---|
| Web app | Next.js / TypeScript |
| API | FastAPI or TypeScript control-plane services |
| Primary DB | PostgreSQL |
| Durable workflow | Temporal |
| Cache/presence | Redis |
| Browser workers | Playwright/Chromium containers |
| Android | Anbox Cloud / Cuttlefish-backed provider |
| Streaming | WebRTC |
| Object storage | S3-compatible |
| Auth | OIDC/SAML capable provider |
| Secrets | KMS + Vault/Secrets Manager |
| Observability | OpenTelemetry + Grafana/Sentry-equivalent |
| Analytics | ClickHouse optional at high event volume |
| Orchestration | Docker locally; Kubernetes/ECS/Nomad in scale deployments |
| IaC | Terraform/OpenTofu |

## Cloud posture

The product should remain cloud/VPC agnostic. No core domain contract should depend on one cloud's proprietary compute primitive. Runtime providers, blob storage, KMS and queue adapters should be interface-driven.
