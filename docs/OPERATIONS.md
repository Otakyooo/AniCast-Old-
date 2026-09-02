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

`scripts/backup-posters.sh` does the same for the shared artwork volume (`mainserver_poster_media`): a verified tarball in `~/anicast/backups/posters/` with 30-day local retention and an offsite copy on the same encrypted remote. It contains title posters and mirrored character/creator portraits. Scheduled weekly (Sundays 03:45, after the DB backup); the pipeline can rebuild missing files from private origins, but a backup restores them without upstream traffic.

Poster restore runbook (`scripts/restore-posters.sh`, defaults to the newest archive):

```bash
# Safe: list, extract and validate every object in the archive (JPEG/PNG
# magic bytes, no zero-byte files); touches nothing.
scripts/restore-posters.sh --verify [archive]

# Destructive: snapshot the current volume to backups/posters/pre-restore-*.tar.gz,
# stop backend/celery, swap the volume contents, restart and probe one poster
# through /api/v1/media/posters/. Requires typing the volume name.
scripts/restore-posters.sh --force [archive]
```

Cron on MainServer runs the backups and verifications (logs in `~/anicast/backups/{backup,restore-verify}.log`):

```cron
15 3 * * *  ~/anicast/scripts/backup-db.sh >> ~/anicast/backups/backup.log 2>&1
45 3 * * 0  ~/anicast/scripts/backup-posters.sh >> ~/anicast/backups/backup.log 2>&1
30 4 * * 0  ~/anicast/scripts/restore-db.sh --verify >> ~/anicast/backups/restore-verify.log 2>&1
10 5 * * *  ~/anicast/scripts/prune-docker-cache.sh >> ~/anicast/backups/maintenance.log 2>&1
```

The newest successful DB dump is recorded in `backups/db/last_backup`. A failed backup sends a Telegram message through the ops bot and exits non-zero; a failed offsite upload still alerts even when the local dump succeeded.

`prune-docker-cache.sh` removes only BuildKit cache older than 24 hours. It does not prune images, containers or volumes, so production and image rollback remain available. The daily limit prevents rapid local-image builds from filling the MainServer root filesystem and triggering `DiskSpaceWarning`.

DB restore runbook:

```bash
# Safe: restore the newest dump into a scratch database, sanity-check it, drop it.
scripts/restore-db.sh --verify [dump]

# Destructive: replace the production database (stops backend and Celery first).
scripts/restore-db.sh --force [dump]
```

`--force` requires typing the production database name, drops and recreates it, restores with `pg_restore`, brings the stack back and waits for backend health. Dumps contain user PII; the Google Drive copy is encrypted with keys that exist only in `~/.config/rclone/rclone.conf` on MainServer.

### Migrating rclone to a project-owned Google Drive client

`rclone` uses a shared Google Drive client_id today; when that client is retired, token refreshes stop working and offsite uploads fail (the backup alert fires). Migration, done once, in order:

1. Create (or pick) an owned Google Cloud project, enable the Drive API and create an OAuth client ID of type *Desktop app*. Note the client id and secret.
2. On MainServer back up the current config: `cp ~/.config/rclone/rclone.conf ~/.config/rclone/rclone.conf.bak-$(date -u +%Y%m%d)` (keep until the new client is proven).
3. The crypt remote `gdcrypt:` sits on top of a plain drive remote; the client credentials live on the **underlying** remote. Run `rclone config`, choose the underlying remote (not `gdcrypt`), set `client_id` and `client_secret`.
4. Re-authorize headless: from a workstation with a browser run `rclone authorize "drive" "<client_id>" "<client_secret>"` and paste the resulting token into the MainServer prompt of `rclone config reconnect <underlying-remote>`.
5. Prove both paths: `rclone touch gdcrypt:.migration-probe && rclone lsl gdcrypt:.migration-probe && rclone delete gdcrypt:.migration-probe`, then run `scripts/backup-db.sh` manually once and confirm the upload message.
6. Keep the `.bak` config for ~30 days, then remove it.

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

Alert rules live in `infra/monitoring/rules/anicast-alerts.yml`: backend down, HTTP 5xx rate, Celery task failures, provider check failures, notification failures, disk below 15%/7%, memory below 10% and monitoring self-checks.

The stack also watches the public site itself: blackbox-exporter probes `https://anicast.online/` and the titles API from the internet (`SiteDown` after 3 minutes, `SiteSlowWarning` above 3s), and a node-exporter on the VPS (`infra/monitoring/vps/compose.yml`, bound to `10.78.0.1:9100` on the AWG interface only — the VPS firewall is disabled) feeds host disk/memory rules for the public host. The nginx metrics sidecar resolves the backend per request, so scraping survives backend container recreation. Alertmanager groups by alert and severity, repeats after 4 hours and sends resolved notifications.

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

Local-image releases: the GHCR credentials stored on MainServer only carry `read:packages` (a push probe returns 403), so a release cut without CI is built on MainServer and shipped to the VPS by hand:

```bash
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker build -t anicast-backend:local-$stamp backend
sed -i "s|^BACKEND_IMAGE=.*|BACKEND_IMAGE=anicast-backend:local-$stamp|" infra/mainserver/.env
docker compose -f infra/mainserver/compose.yml run --rm --no-deps --entrypoint python backend manage.py migrate --plan
docker compose -f infra/mainserver/compose.yml up -d backend celery-worker celery-beat

docker build --build-arg NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=anicast_auth_bot \
  --build-arg NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME=anicast_push_bot \
  -t anicast-frontend:local-$stamp frontend
docker save anicast-frontend:local-$stamp | gzip -1 > /tmp/frontend-$stamp.tar.gz
scp /tmp/frontend-$stamp.tar.gz root@10.78.0.1:/tmp/
ssh root@10.78.0.1 "gunzip -c /tmp/frontend-$stamp.tar.gz | docker load"
ssh root@10.78.0.1 "sed -i 's|^FRONTEND_IMAGE=.*|FRONTEND_IMAGE=anicast-frontend:local-$stamp|' /opt/anicast/infra/vps/.env"
ssh root@10.78.0.1 "cd /opt/anicast/infra/vps && docker compose up -d frontend"
```

The frontend build args must be passed explicitly: `NEXT_PUBLIC_*` values are inlined at build time, and omitting them silently disables the Telegram login and notification prompts. Take a verified `pg_dump` first, keep the previous digests written down (image-only rollback is the only automatic path), and delete the transferred tarball from both hosts afterwards. Restore GHCR digest pins as soon as a token with `write:packages` is available, since local tags carry no provenance.

Do not run an unconstrained Next.js production build on MainServer while it serves traffic. The host has one CPU and a build can push PostgreSQL/backend into swap, causing multi-second TTFB. Prefer CI or a separate build host; an emergency local build must use low CPU/I/O priority and be run once after all source changes.

## Catalog metadata import

`fetch_catalog_metadata` pulls the configured upstream catalog metadata (Russian and English names, Japanese originals, genres with translations, artwork and episode counts) and emits an `import_catalog` JSON payload. Upstream endpoints are server-side implementation details: never expose their brand or URLs in public API, HTML, SEO or social metadata.

```bash
# run from the backend directory (host networking avoids container DNS quirks)
docker run --rm --network host -v $PWD:/app -e DJANGO_DATABASE_URL=sqlite:///db.sqlite3   -w /app --entrypoint python anicast-backend:local   manage.py fetch_catalog_metadata --limit 100 --output /app/batch.json
# validate (dry-run) then apply on the production stack
docker cp batch.json mainserver-backend-1:/tmp/batch.json
docker exec mainserver-backend-1 python manage.py import_catalog /tmp/batch.json
docker exec mainserver-backend-1 python manage.py import_catalog /tmp/batch.json --apply
```

The import is idempotent (`update_or_create` by slug and stable catalog id), rate-limit friendly and never creates playback sources — rights and providers stay untouched.

The importer also fills franchises and characters. GraphQL roles map `Main` to `protagonist` and other roles to `supporting`; biographies, localized names and portrait origins stay private until mirrored. A full 100-title run with characters takes roughly 15 minutes. Episode scheduling remains owned by Kodik `material_data.next_episode_at`.

## Kodik library synchronization

`sync_kodik` is dry-run first and accepts either a stable catalog-id title slug or
`--all`. It imports players only for the local AniCast library; it does not bulk
copy unrelated Kodik records. Each pass also:

- creates newly discovered episode rows;
- records `material_data.next_episode_at` on the next episode for `/schedule`;
- imports duration and director/producer/writer/composer/designer credits;
- marks disappeared sources unavailable only after a complete provider response.

Kodik season numbers are provider-side metadata, not AniCast season numbers.
The normal pass therefore does not send a hard-coded `season=1`: it consumes the
positive season key returned for the exact catalog id and ignores season `0`
when a positive season exists (extras); season `0` remains a fallback for OVAs.
For a completed title, season-zero bonuses fill only the remainder up to the
official catalog episode count (for example Bakemonogatari 13–15), never
creating episodes beyond that boundary.
Movies and one-shot specials use their direct player link. `--season N`
remains an explicit diagnostics override.

Initial production activation is explicit and auditable. The reference is not a
password or API token; it describes the verified provider entitlement:

```bash
docker exec mainserver-backend-1 python manage.py sync_kodik --all
docker exec mainserver-backend-1 python manage.py sync_kodik --all --apply --activate \
  --rights-reference="Kodik account entitlement for anicast.online"
```

The API token stays in `KODIK_API_TOKEN`. Never place the portal password in a
command, commit or deployment manifest. After activation, Celery Beat runs
`catalog.tasks.sync_kodik_library` hourly in bounded 20-title slices and stores
its cursor in Redis. Revoke playback without deleting metadata by disabling the
Kodik provider in `/staff/`; sources and schedule data remain available for
audit and a later reactivation.

## Episode names and dates

`sync_episode_metadata` fills missing episode names and confirmed calendar dates
from the Jikan/MAL episode endpoint. English and Japanese names are stored as
separate translations; the English name is the safe fallback when no Russian
episode title exists. Existing editorial names are never overwritten. Jikan's
date-only value never replaces a more precise Kodik `air_at` timestamp.

```bash
docker exec mainserver-backend-1 python manage.py sync_episode_metadata --all
docker exec mainserver-backend-1 python manage.py sync_episode_metadata --all --apply
```

The command is dry-run first, retries bounded upstream failures and caps a title
at 25 pages. Celery Beat refreshes up to three titles with missing names every
15 minutes so successful rows leave the retry queue and temporary upstream 504s
converge without exceeding the public API rate limit.

Artwork: posters prefer the largest available catalog artwork (`maximum_image_url`, falling back to `large_image_url`). Temporary upstream failures are retried by the scheduled mirror pipeline. The browser never receives an upstream artwork URL.

Artwork mirroring: title posters, character portraits and creator photos live in the shared `poster_media` Compose volume and are served by Django from `https://anicast.online/api/v1/media/*` with `Cache-Control: public, max-age=31536000, immutable`. Public serializers return AniCast media URLs only. Provider origins live in private `*_origin_url` fields and are never serialized. Downloads run only in operator/background jobs and require allowlisted HTTPS on port 443 without credentials or fragments, bounded redirects and size, valid JPEG/PNG bytes and minimum dimensions. A public request never waits for an upstream; failure keeps the local image or shows the brand fallback, never a hotlink.

Portraits are mirrored explicitly in parallel before exposure. The command is dry-run unless `--apply` is explicit:

```bash
docker exec mainserver-backend-1 python manage.py mirror_portraits
docker exec mainserver-backend-1 python manage.py mirror_portraits --title 21-one-piece --apply --workers 8
docker exec mainserver-backend-1 python manage.py mirror_portraits --apply --workers 8
```

After a full pass, verify that character and creator `image_url` values point to `/api/v1/media/posters/`, public API/HTML contain no upstream host, and `image_origin_url` remains private for refresh and recovery. A failed item stays eligible for a later pass.

The Celery Beat task `catalog.tasks.refresh_title_posters` (dedicated `posters` queue so batches never delay provider health checks; every 6 hours, budget-driven — it keeps working until the 1300 s soft-limit budget is spent or the 120-outcome hard cap is hit, and stops starting new titles in time to respect its time limits) keeps upgrading titles until each sits at the `m` tier, so posters converge to the best artwork automatically once Jikan recovers — no manual reruns. Candidates are prioritised: broken/missing local files first (direct viewer impact), then fallback-tier art awaiting a MAL upgrade, then large/kitsu-tier re-probes; within a bucket sampling is random for fair retry spread. Titles at the `m` tier are dropped from the queue without probes, and titles that can never improve (no MAL id in the slug, no allowlisted source) are dropped too. Every mirrored row records its remote source in `titles.poster_origin_url`; a missing local file downgrades the title back to an adoption candidate, so the pipeline self-heals after volume loss. Outcomes are exposed as `anicast_poster_refresh_total{result=maximum|large|kitsu|mirrored|current|unavailable|invalid|error}` with `PosterRefreshErrors`/`PosterRefreshInvalid` Prometheus alerts on sustained failure spikes. Manual control stays available:

```bash
docker exec mainserver-backend-1 python manage.py backfill_posters          # dry-run
docker exec mainserver-backend-1 python manage.py backfill_posters --apply  # mirror + upgrade
```

Kitsu fallback tier `k` (2026-08-24): while Jikan cannot serve MAL art, the pipeline resolves `mal_id -> kitsu_id` through the ani.zip offline mapping (`api.ani.zip/mappings`, host allowlisted together with `kitsu.io`) and adopts Kitsu `posterImage.original` from `media.kitsu.app`. Adoption is pixel-based: a candidate replaces stored artwork only when its downloaded dimensions strictly exceed the current file (area comparison), so no title ever loses quality when tiers compete. A later MAL `l` or `m` still wins over an existing `k` through the same comparison path. Both lookup hosts fail closed to `None` and simply skip the fallback.

Rollback uses the database dump plus the verified media-volume backup. Do not restore public fields to upstream URLs. The portrait migration is reversible for application rollback, while new local files remain compatible with the established `/api/v1/media/posters/` route.

## Title detail and episode pages

`/api/v1/titles/<slug>/` paginates the embedded episode list (`episodes_page`, `episodes_page_size`, default 20, max 50) and reports the total in `episodes_count`, so long-running series no longer serialize thousands of episodes in one response. `episode_sources=0` is the opt-in compact mode used by the title UI: episode rows omit playback sources and avoid their queries; the dedicated episode endpoint still returns playback-gated sources. Metadata additionally requests one episode and one character with a 60-second revalidation window.

All server-side Next.js request paths, including public profiles and collections, use `INTERNAL_API_BASE_URL` over AWG and send `X-AniCast-Internal-Token`. Store the same random value (at least 32 characters) as `INTERNAL_API_TOKEN` on MainServer and VPS. Caddy strips that header from every public `/api/*` request. Valid safe internal requests use the separate `ssr=600/min` bucket; public anonymous traffic remains at `60/min`, and frontend retry is limited to transport failures only.

Every header-secret comparison (`INTERNAL_API_TOKEN`, `METRICS_BEARER_TOKEN`, both Telegram webhook secrets) goes through `common.security.constant_time_equals`. Django decodes request headers as latin-1, so a client can send code points 128–255; `hmac.compare_digest` raises `TypeError` on non-ASCII `str`, which on the default throttle path would have turned one hostile header into a 500 on every API request. Comparing bytes keeps a hostile header an ordinary mismatch, and an unset secret fails closed.

Throttling is layered. Anonymous traffic uses `anon=60/min` per address, authenticated traffic `user=240/min` per account (DRF's `AnonRateThrottle` skips logged-in requests, so without the user bucket one cheap account could hammer account summary, recommendations and continue-watching without limit), trusted SSR `ssr=600/min`, login and registration `auth=10/min` per address, playback `playback=30/min`. `DJANGO_NUM_PROXIES` (default 1) matters here: exactly one trusted proxy sits in front, and without it DRF keys buckets on the whole `X-Forwarded-For`, so a client-supplied prefix would mint a fresh bucket per request and defeat every limit.

The visit counter (`/api/v1/analytics/visit/`) is a plain Django view outside the DRF defaults, and both of its own guards are advisory: the bot check reads the User-Agent and the dedupe check reads a cookie the client controls. Only the counting branch is throttled at `visit=600/hour` per address, so returning browsers with their signed cookie never spend the budget, and a cookie-less script can no longer take a row lock on today's counter per request. Exhausting the bucket stops counting and still answers 200 — it never fails a page load for a vanity metric.

Gunicorn runs 2 workers × 2 threads with `--timeout 30`, `--graceful-timeout 30`, `--keep-alive 5` and request recycling at 2000 (±200 jitter). The default single sync worker meant one slow request blocked the whole API including the container healthcheck. The timeout sits above the frontend's 10-second fetch budget so gunicorn never kills a request the client still awaits. With `CONN_MAX_AGE=60` (`DJANGO_CONN_MAX_AGE`) and `CONN_HEALTH_CHECKS`, persistent connections stay bounded at 4 per backend container. Access logging stays off: `ObservabilityMiddleware` already emits one structured JSON line per request, and gunicorn's plain-text log would mix two formats into the same stdout stream.

The metrics endpoint aggregates 24-hour availability in bounded SQL and groups provider/source counts. Keep this path bounded: Prometheus scrapes every 30 seconds and a full Python scan of raw probe history would block a request-serving worker.

## VPS firewall

ufw is enabled with `deny (incoming)`, `deny (routed)` by default. Allowed: TCP 22/80/443, **UDP 443 (AmneziaWG listen port — never remove, the tunnel and the site depend on it)**, everything on `awg0` (incoming and forwarded — MainServer reaches the internet through this tunnel NAT). Before changing rules, keep a public-SSH session open as a recovery path.

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

## Deploy pipeline rehearsal

The formal pipeline has not executed against production yet: the live stacks run under compose project names `mainserver` and `vps` (directory defaults), while `deploy.sh`/`rollback.sh`/`verify-deploy.sh` default to `anicast-mainserver`/`anicast-vps`. Running the pipeline cold under its default names would spawn parallel stacks with fresh, empty volumes. All three scripts therefore honor `ANICAST_PROJECT_MAINSERVER` and `ANICAST_PROJECT_VPS`; until a deliberate migration to the canonical names, every pipeline command uses the live-name overrides.

Rehearsal checklist (quiet hours):

1. Preconditions: no firing alerts, current image digests written down, fresh verified backup (`scripts/backup-db.sh` plus `scripts/restore-posters.sh --verify` on the latest poster archive).
2. Prepare manifests for the pending release: `scripts/release-manifest.sh <git-sha>` and preview migrations once (`docker compose --project-name mainserver --env-file infra/mainserver/.env -f infra/mainserver/compose.yml run --rm backend python manage.py migrate --plan` — must be expand-only).
3. MainServer: `sudo ANICAST_PROJECT_MAINSERVER=mainserver scripts/deploy.sh mainserver /tmp/mainserver-release.env`. Success: check/migrate pass, postgres/redis/backend/celery-worker/celery-beat healthy, `deployment verified`.
4. Public smoke: the three curl probes from the Deploy section.
5. VPS: `sudo ANICAST_PROJECT_VPS=vps scripts/deploy.sh vps /tmp/vps-release.env`, then public smoke again.
6. Rollback drill, proving both directions on the real stack: `sudo ANICAST_PROJECT_VPS=vps scripts/rollback.sh vps` (previous digest serves traffic), then re-run the step-5 deploy forward. The MainServer rollback drill is optional in the same window — it is image-only as well.
7. Record the outcome in `docs/IMPLEMENTATION_STATUS.md`. State files accumulate under `/var/lib/anicast/releases/<stack>/`.

Adoption caveats: the first pipeline run moves image selection from `infra/<stack>/.env` into the release manifest chain (`current.env`). Keep `BACKEND_IMAGE`/`FRONTEND_IMAGE` out of further hand edits afterwards, or the next manual `compose up -d` silently diverges from the recorded releases. The hermetic test (`scripts/tests/deploy_rollback_test.sh`, part of `scripts/validate.sh`) covers both the automatic-rollback failure path and the happy-path promotion to `current.env`.

## Validation

```bash
sh scripts/validate.sh
cd backend
DJANGO_DATABASE_URL=sqlite:///db.sqlite3 python -m pytest
ruff check .
DJANGO_DATABASE_URL=sqlite:///db.sqlite3 mypy .
DJANGO_DATABASE_URL=sqlite:///db.sqlite3 python manage.py makemigrations --check --dry-run
DJANGO_DATABASE_URL=sqlite:///db.sqlite3 python manage.py check
# The deploy audit runs against production-shaped settings and is gated: on
# SQLite, SECURE_SSL_REDIRECT is off by design, so the check could only emit
# warnings nobody could act on and nothing could enforce.
DJANGO_SECRET_KEY=ci-only-secret-with-more-than-fifty-characters-and-plenty-of-variety-9182736450 \
  DJANGO_DEBUG=0 DJANGO_ALLOWED_HOSTS=anicast.online \
  DJANGO_CSRF_TRUSTED_ORIGINS=https://anicast.online \
  python manage.py check --deploy --fail-level WARNING
pip-audit --strict --requirement requirements.txt
cd ../frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

`scripts/validate.sh` runs shell syntax checks, Compose config validations for all three stacks, promtool/amtool checks of the monitoring configuration with placeholder secrets, the hermetic deploy/rollback test and rejects public metrics routes in Caddy. CI additionally builds both images and validates Caddy with the official image.

`pip-audit` is part of the pinned requirements and gates CI. Pinned dependencies go stale silently, so a missed security release must fail the build instead of waiting to be discovered: the audit is what turns the pins into a maintained set rather than a snapshot. `DJANGO_SECRET_KEY` has no safe fallback in a non-SQLite deployment — the placeholder key signs sessions, the visit cookie and playback tokens, and the guard fires regardless of `DJANGO_DEBUG` so a stack accidentally booted with debug on cannot run on a publicly known key.
