# Deployment

## Local

```bash
cp .env.example .env
docker compose up --build
```

Or run directly with Python and Playwright.

## Production topology

Deploy at least three logical planes:

1. **Control plane** — stateless API/web services + PostgreSQL.
2. **Runtime plane** — isolated browser/Android workers on dedicated compute.
3. **Observability/data plane** — telemetry, artifacts and cost analytics.

## Kubernetes

Recommended production objects:
- control-plane Deployment + HPA
- orchestrator Deployment
- worker pool(s) using node selectors/taints
- streaming gateway Deployment
- PostgreSQL managed externally or StatefulSet only for non-production
- Redis/Temporal according to chosen operating model
- NetworkPolicies
- PodDisruptionBudgets
- workload identity
- secrets through external KMS/Vault integration

## Cloud/VPC agnostic design

Adapters should isolate provider-specific behavior:
- BlobStore
- KeyProvider
- RuntimeCapacityProvider
- Queue/Workflow provider
- LoadBalancer/Ingress
- Metrics exporter

Keep domain services independent from AWS/Azure/GCP SDKs.

## Release process

- merge to main after CI
- build immutable image
- generate SBOM
- vulnerability scan
- deploy to staging
- run smoke/integration tests
- canary production runtime workers
- promote control plane
- preserve rollback image/schema plan

## Backups

- PostgreSQL PITR
- versioned object storage
- state snapshot checksums
- periodic restore tests

## Secrets

No secrets in Git, image layers or CI logs. Use environment injection only for local development; production uses workload identity and a secrets provider.
