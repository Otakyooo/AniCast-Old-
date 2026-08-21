# AniCast observability, deploy and rollback

## Boundaries

Production topology remains VPS -> AmneziaWG/WireGuard -> MainServer. Caddy exposes only `/api/*`, `/staff*` and `/static/*` from Django. `/health/*` and `/internal/metrics` are not public routes. No external monitoring service is required.

Application logs are written to stdout as one JSON object per line. Django logs only allowlisted operational fields and never request/response bodies, query strings, headers, cookies, user identifiers, task arguments, source URLs or exception text. Caddy writes JSON access logs; Docker rotates all service logs at five 10 MiB files. Next.js process output remains native stdout while frontend HTTP traffic is captured by Caddy.

## Metrics

Set a unique random `METRICS_BEARER_TOKEN` of at least 32 characters in `/etc/anicast/mainserver.env`. The endpoint is available only over the private MainServer listener:

```bash
curl --fail --silent --show-error \
  -H "Authorization: Bearer $METRICS_BEARER_TOKEN" \
  -H "X-Forwarded-Proto: https" \
  http://10.78.0.2:8000/internal/metrics
```

Configure the MainServer firewall to allow TCP/8000 only from VPS peer `10.78.0.1`. A self-hosted Prometheus may scrape this endpoint from the VPS over `awg0`; keep its UI bound to `127.0.0.1` and access it through SSH port forwarding. Never add `/internal/metrics` or a Prometheus port to the public Caddyfile.

Counters use the shared Redis cache and reset after Redis data loss. Gauges for providers and sources are read from PostgreSQL at scrape time. Labels are fixed to endpoint groups, method/status families, known Celery tasks and bounded result enums.

Key signals:

- `anicast_http_requests_total` and `anicast_http_request_duration_seconds`;
- `anicast_celery_tasks_total`;
- `anicast_source_checks_total` and `anicast_source_check_duration_seconds`;
- `anicast_notification_deliveries_total`;
- `anicast_providers` and `anicast_sources`.

Alert at minimum on repeated backend readiness failures, HTTP 5xx increase, provider check failures, Celery task failures, notification failures, unhealthy Compose services, stale AWG handshake, disk pressure and missing backups.

## Release manifests

Build and publish backend/frontend images outside the hosts, then resolve them to immutable digests. A MainServer release file contains no secrets:

```dotenv
BACKEND_IMAGE=registry.example/anicast-backend@sha256:<digest>
RELEASE_SHA=<git-sha>
ANICAST_ENV_FILE=/etc/anicast/mainserver.env
```

A VPS release file uses:

```dotenv
FRONTEND_IMAGE=registry.example/anicast-frontend@sha256:<digest>
RELEASE_SHA=<git-sha>
ANICAST_ENV_FILE=/etc/anicast/vps.env
```

Restrict `/etc/anicast/*.env` to root and the deployment account. Never place tokens/passwords in a release manifest, command line, Compose output or Git.

## Deploy

Deploy MainServer first and VPS second. The script acquires a per-stack lock, validates an immutable digest, rotates `current.env` to `previous.env`, pulls, runs checks and migrations on MainServer, starts without rebuilding, waits for every healthcheck and runs smoke probes.

```bash
sudo scripts/deploy.sh mainserver /tmp/mainserver-release.env
sudo scripts/deploy.sh vps /tmp/vps-release.env
```

MainServer verification requires PostgreSQL, Redis, Django readiness, Celery worker ping and Celery Beat health. VPS verification requires frontend and Caddy health plus a loopback frontend request. Run public smoke separately after both stacks pass:

```bash
curl --fail --silent --show-error --max-time 15 https://anicast.online/ >/dev/null
curl --fail --silent --show-error --max-time 15 \
  'https://anicast.online/api/v1/titles/?page_size=1' >/dev/null
test "$(curl -sS -o /dev/null -w '%{http_code}' https://anicast.online/internal/metrics)" != 200
```

Before MainServer deployment, create and verify a PostgreSQL logical backup according to the existing host backup policy. The deploy script intentionally does not claim to implement backup retention or restore verification.

## Automatic rollback

Any failed Compose health or smoke gate triggers `scripts/rollback.sh` for that stack and verifies the previous manifest with the same probes. Manual rollback is:

```bash
sudo scripts/rollback.sh mainserver
sudo scripts/rollback.sh vps
```

Rollback changes application images only. It never restores PostgreSQL automatically because traffic may have written data after migration. Migrations must therefore follow expand/contract and keep the previous application release compatible. A destructive migration requires a separately approved maintenance and restore plan; do not use automatic deployment for it.

If both hosts were changed and VPS verification fails, roll back VPS first and then MainServer when release compatibility requires it. Inspect `/var/lib/anicast/releases/<stack>/{current,previous,failed}.env` and JSON logs for the incident record.

## Validation

```bash
sh scripts/validate.sh
cd backend
python -m pytest
ruff check .
mypy .
DJANGO_DATABASE_URL=sqlite:///db.sqlite3 python manage.py makemigrations --check --dry-run
DJANGO_DATABASE_URL=sqlite:///db.sqlite3 python manage.py check
DJANGO_DATABASE_URL=sqlite:///db.sqlite3 DJANGO_SECRET_KEY=ci-only-long-secret python manage.py check --deploy
cd ../frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

`scripts/validate.sh` runs shell syntax checks, both Compose config validations and rejects public metrics routes in Caddy. CI additionally builds both images and validates Caddy with the official image.
