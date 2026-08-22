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

Configure the MainServer firewall to allow TCP/8000 only from VPS peer `10.78.0.1`. The self-hosted Prometheus runs on MainServer (see Monitoring stack) and scrapes through an nginx sidecar attached to the `mainserver_internal` Docker network; keep its UI bound to `127.0.0.1` and access it through SSH port forwarding. Never add `/internal/metrics` or a Prometheus port to the public Caddyfile.

Counters use the shared Redis cache and reset after Redis data loss. Gauges for providers and sources are read from PostgreSQL at scrape time. Labels are fixed to endpoint groups, method/status families, known Celery tasks and bounded result enums.

Key signals:

- `anicast_http_requests_total` and `anicast_http_request_duration_seconds`;
- `anicast_celery_tasks_total`;
- `anicast_source_checks_total` and `anicast_source_check_duration_seconds`;
- `anicast_notification_deliveries_total`;
- `anicast_providers` and `anicast_sources`.

Alert at minimum on repeated backend readiness failures, HTTP 5xx increase, provider check failures, Celery task failures, notification failures, unhealthy Compose services, stale AWG handshake, disk pressure and missing backups.

## Backups

`scripts/backup-db.sh` creates a verified `pg_dump -Fc` dump in `~/anicast/backups/db/`, proves it is readable with `pg_restore --list`, applies retention (14 daily dumps plus Sunday dumps for 60 days; manual `predeploy-*` dumps are never removed) and copies the dump to an encrypted Google Drive remote (`rclone crypt` on top of the user-owned `AniCast Backups` folder). On any failure the script sends a Telegram message through the ops bot configured in `infra/monitoring/.env` and exits non-zero.

Cron on MainServer runs the backup daily at 03:15 UTC-local and a scratch-database restore verification on Sundays at 04:30. Logs live in `~/anicast/backups/{backup,restore-verify}.log`; the newest successful dump is recorded in `backups/db/last_backup`.

Restore runbook:

```bash
# Safe: restore the newest dump into a scratch database, sanity-check it, drop it.
scripts/restore-db.sh --verify [dump]

# Destructive: replace the production database (stops backend and Celery first).
scripts/restore-db.sh --force [dump]
```

`--force` requires typing the production database name, drops and recreates it, restores with `pg_restore`, brings the stack back and waits for backend health. Dumps contain user PII; the Google Drive copy is encrypted with keys that exist only in `~/.config/rclone/rclone.conf` on MainServer.

`rclone` uses the shared Google Drive client_id today; when that client is retired, create a project-owned OAuth client_id and re-authorize, otherwise offsite uploads stop refreshing.

## Monitoring stack

`infra/monitoring/compose.yml` runs on MainServer as a separate Compose project joined to the external `mainserver_internal` network:

- Prometheus (retention 15d, `127.0.0.1:9090`) scrapes the backend through the nginx sidecar, which adds the `X-Forwarded-Proto: https` header Django requires and keeps the bearer token flow intact;
- Alertmanager (`127.0.0.1:9093`) delivers alerts with the native Telegram receiver;
- node-exporter provides host disk, memory and CPU metrics;
- every service is memory-limited; the whole stack uses roughly 110 MiB.

Access the UIs from a workstation:

```bash
ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 anicast-main
# Prometheus: http://localhost:9090  Alertmanager: http://localhost:9093
```

Alert rules live in `infra/monitoring/rules/anicast-alerts.yml`: backend down, HTTP 5xx rate, Celery task failures, provider check failures, notification failures, disk below 15%/7%, memory below 10% and monitoring self-checks. Alertmanager groups by alert and severity, repeats after 4 hours and sends resolved notifications.

Secret files under `infra/monitoring/secrets/` (gitignored) are mounted read-only: `metrics-token` mirrors `METRICS_BEARER_TOKEN`, `telegram-token` and `telegram-chat-id` carry the ops bot credentials. After changing them, `docker compose -f infra/monitoring/compose.yml restart alertmanager`.

## Image publication

GitHub Actions publishes both images to GHCR on every push to `main` and on `v*` tags (`.github/workflows/publish.yml`) using the built-in `GITHUB_TOKEN`; the job summary prints ready-to-use digest lines. Resolve a tag into a deploy release manifest with:

```bash
scripts/release-manifest.sh <git-sha>      # or --tag main
```

The repository is private, so packages are private: hosts that pull need `docker login ghcr.io` with a token that has `read:packages` (both hosts are logged in as of 2026-08-22).

Both production stacks run digest-pinned GHCR images (`BACKEND_IMAGE`/`FRONTEND_IMAGE` in the stack `.env`). Release switch:

```bash
scripts/release-manifest.sh <git-sha>          # prints digests for the commit
# mainserver: put BACKEND_IMAGE=ghcr.io/...@sha256:... into infra/mainserver/.env
cd infra/mainserver && docker compose pull backend && docker compose up -d
# vps: put FRONTEND_IMAGE=...@sha256:... into /opt/anicast/infra/vps/.env
cd /opt/anicast/infra/vps && docker compose pull frontend && docker compose up -d
```

Rollback: point the image variable back to the previous digest (or to the local fallback tags `anicast-backend:local` / `vps-frontend:latest`) and `up -d` again. The formal `deploy.sh` pipeline (project names `anicast-*`, state dirs, automatic rollback) remains available for a future stack migration.

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

`scripts/validate.sh` runs shell syntax checks, Compose config validations for all three stacks, promtool/amtool checks of the monitoring configuration with placeholder secrets, the hermetic deploy/rollback test and rejects public metrics routes in Caddy. CI additionally builds both images and validates Caddy with the official image.
