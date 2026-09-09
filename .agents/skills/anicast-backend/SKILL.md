---
name: anicast-backend
description: Implement or review Anicast Django/DRF APIs, models, migrations and Celery tasks, including frontend contracts and data boundaries. Use for backend behavior or data architecture; use anicast-ops for running deployments and recovery.
---

# Anicast backend

Read [current state](../../../docs/IMPLEMENTATION_STATUS.md), then the relevant
section of [application operations](../../../docs/operations/APPLICATION.md).
For catalog/player changes use [TITLE_DATA_AND_PLAYER](../../../docs/TITLE_DATA_AND_PLAYER.md);
for public identity/privacy use [SOCIAL_PROFILES](../../../docs/SOCIAL_PROFILES.md).
Read the nearest view, serializer, model and consumer in `frontend/lib` before
changing an API contract. Preserve modular Django apps; add service boundaries
only for a concrete requirement and record the affected state owner in an ADR.

## Data and API contracts

- Sessions live in PostgreSQL. Mutations require the existing session/CSRF/Origin
  contract and object-level permissions; public profile IDs are not authorization.
- Inspect model constraints and existing records before schema changes. Use
  expand/contract for compatibility with the retained application image. Describe
  irreversible changes honestly; image rollback never restores a database.
- Bound list queries, payloads and provider batches. Use select/prefetch where
  measured query growth warrants it; retain pagination and language-aware behavior.
- Private and authenticated responses stay private/no-store. Public catalog cache
  headers vary by locale/cookie; reuse established cache decorators.
- Trusted SSR uses `frontend/lib/internal-api.ts` and a private header. Public
  Caddy strips that header; `common.security` compares secrets in constant time.
  Keep LiveRatesMixin so settings overrides actually affect throttle rates.

## State and background work

Broker/results, control and ephemeral Redis are different services. Django cache
alias `default` owns throttles/locks/cursors; `ephemeral` owns disposable counters.
Cache eviction must not lose coordination or block enqueue. Preserve queue routes:
default/notifications versus providers/posters/maintenance/analytics, concurrency 1
per worker. Bound retries, external timeouts and repeated side effects; do not
raise concurrency based on the owner's future RAM upgrade.

Use synthetic users, captured notification sinks and in-memory email for tests.
Never treat a mocked provider or captured email as verified real delivery.
Inspect privacy, repeated requests, failure recovery and affected consumers in
reviews; report a concrete failure scenario, not a generic checklist finding.
Run the relevant [checks](../../../docs/operations/DEPLOYMENT.md#validation).
`backend/mypy.ini` is the actual typing contract; it is not strict mode today.
