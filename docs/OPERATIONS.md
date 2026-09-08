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

Configure the MainServer firewall to allow TCP/8000 only from VPS peer `10.78.0.1`. The self-hosted Prometheus runs on MainServer (see Monitoring stack) and scrapes through an nginx sidecar attached to the scrape-only `mainserver_metrics` Docker network; keep its UI bound to `127.0.0.1` and access it through SSH port forwarding. Never add `/internal/metrics` or a Prometheus port to the public Caddyfile.

## Redis

Redis requires a password (`REDIS_PASSWORD`, passed to `--requirepass`), and the same value must appear in `CACHE_URL`, `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` as `redis://:PASSWORD@redis:6379/N`. This is not defence in depth: Redis holds the Celery broker, task names are public, and anything that can write to the broker executes code in the worker. An unauthenticated Redis on a shared Docker network is a remote code execution path, not a cache.

Rotating the password means editing four values in the env file and recreating everything that connects, in one step:

```bash
docker compose -f infra/mainserver/compose.yml up -d
```

The healthcheck reads `REDISCLI_AUTH` from the environment, so `redis-cli ping` from outside the container returns `NOAUTH Authentication required` — that is the expected, healthy answer.

Counters use the shared Redis cache and reset after Redis data loss. Gauges for providers and sources are read from PostgreSQL at scrape time. Labels are fixed to endpoint groups, method/status families, known Celery tasks and bounded result enums.

Key signals:

- `anicast_http_requests_total` and `anicast_http_request_duration_seconds`;
- `anicast_celery_tasks_total`;
- `anicast_source_checks_total` and `anicast_source_check_duration_seconds`;
- `anicast_notification_deliveries_total`;
- `anicast_providers` and `anicast_sources`.

Alert at minimum on repeated backend readiness failures, HTTP 5xx increase, provider check failures, Celery task failures, notification failures, unhealthy Compose services, stale AWG handshake, disk pressure and missing backups.

## Provider health checks

`catalog.tasks.check_provider_sources` runs every 10 minutes on the `providers` queue and probes a bounded slice: at most 150 sources per run, with a 420-second wall-clock budget that stops new probes before the Celery soft limit fires. A Redis cursor (`catalog:source-check-cursor`) walks the whole catalog across runs and wraps at the end, so a shrinking catalog cannot strand it past the last id.

The bound is not optional. With ~29k sources and a 10-second HEAD timeout each, a full sweep cannot finish inside `CELERY_TASK_SOFT_TIME_LIMIT`: the previous unbounded version was killed mid-batch every 10 minutes, so the tail of the catalog was never checked at all. If you need a faster full sweep, run the task manually with a larger `limit` rather than raising the schedule frequency:

```bash
docker exec mainserver-backend-1 python -c \
  "from catalog.tasks import check_provider_sources; print(check_provider_sources(limit=150))"
```

`SourceHealthCheck` grows by one row per probed source per run, so the task prunes rows older than 14 days on every run (`HEALTH_CHECK_RETENTION_DAYS`). That window covers the rolling windows the staff dashboard renders; older rows only consume space. The `pruned` count is part of the task result and of its completion log line.

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

`infra/monitoring/compose.yml` runs on MainServer as a separate Compose project joined to the external `mainserver_metrics` network:

- Prometheus (retention 15d, `127.0.0.1:9090`) scrapes the backend through the nginx sidecar, which adds the `X-Forwarded-Proto: https` header Django requires and keeps the bearer token flow intact;
- Alertmanager (`127.0.0.1:9093`) delivers alerts with the native Telegram receiver;
- node-exporter provides host disk, memory and CPU metrics;
- every service is memory-limited; the whole stack uses roughly 110 MiB.

The sidecar joins `mainserver_metrics`, a scrape-only network that carries the backend and nothing else. It previously joined `mainserver_internal`, which also carries PostgreSQL and Redis, so the monitoring stack held a path into the application's data tier for the sake of one HTTP endpoint. Docker DNS answers are per-network, so a container attached only to `mainserver_metrics` cannot even resolve `postgres` or `redis`. Keep it that way: never add a data-tier service to that network, and never reattach monitoring to `mainserver_internal`.

Access the UIs from a workstation:

```bash
ssh -L 9090:127.0.0.1:9090 -L 9093:127.0.0.1:9093 anicast-main
# Prometheus: http://localhost:9090  Alertmanager: http://localhost:9093
```

Alert rules live in `infra/monitoring/rules/anicast-alerts.yml`: backend down, HTTP 5xx volume and per-endpoint-group error ratio, pending migrations, alert-delivery failures, Celery task failures, provider check failures, notification failures, disk below 15%/7%, memory below 10% and monitoring self-checks.

Three of those exist because of specific incidents:

- `EndpointGroupErrorRatio` catches what the absolute 5xx counter misses. On a low-traffic site, one endpoint group answering 500 for every request produces few errors per minute; a ratio does not care about volume. During the 2026-09-02 incident the API group ran at 48% errors while the site as a whole looked healthy.
- `PendingMigrations` alerts on the cause rather than the symptom. `anicast_pending_migrations` is exported by `/internal/metrics`; a model referencing columns the schema lacks answers 500 on every request that touches them, and that state went unnoticed for an hour because only the symptom was visible.
- `AlertDeliveryFailing` watches the notification path itself. Every other rule is worthless if the message never lands: Alertmanager retried Telegram 274 times and gave up each time while egress from MainServer was blocked, and nothing said so. The expression sums by `integration` on purpose — the counter also carries a `reason` label, so the bare metric raises one alert per failure reason for the same broken channel.

## Telegram relay

`api.telegram.org` is unreachable from MainServer. It times out from the host, from the backend container and from Alertmanager, while the same request from the VPS returns 302 and unrelated upstreams (Jikan) work fine from MainServer — so this is not DNS, not routing and not a general egress block. Everything Telegram-shaped therefore goes through a relay Caddy exposes on the VPS inside the AmneziaWG tunnel:

```
MainServer (backend, Celery, Alertmanager, backup scripts)
  -> http://10.78.0.1:8443/bot<token>/<method>   (plain HTTP, inside the tunnel)
  -> VPS Caddy
  -> https://api.telegram.org                    (HTTPS, verified)
```

Consumers, all pointing at the same relay:

- `TELEGRAM_API_BASE_URL` in `infra/mainserver/.env` — user notifications (`push/telegram.py`). Unset means direct upstream, which is the right default for local development and any host with working egress.
- `api_url` in `infra/monitoring/alertmanager.yml` — alert delivery.
- `TELEGRAM_API_BASE_URL` (same default) in `scripts/backup-db.sh` and `scripts/backup-posters.sh`. These were calling Telegram directly, which meant a failing backup reported itself only to stderr on a cron run — the alert was discarded exactly when it mattered.

Four things keep the relay from becoming an open proxy, and all four matter:

1. `bind 10.78.0.1` — **this is the actual restriction**. A site address in Caddy only matches the Host header; without `bind` the listener comes up on `*:8443`. Verified in production: the first deploy showed `*:8443` in `ss -tlnp` and only the firewall stood between it and the internet.
2. `remote_ip 10.78.0.0/24` — a routing or firewall mistake alone does not expose it.
3. `path /bot*` and `method POST GET` — the Bot API shape, not a general-purpose proxy.
4. No `log` directive on that site. The bot token is part of the URL path, so an access log would write live credentials to disk on every notification. Do not add one for debugging without redacting the path.

Verify the relay after touching the Caddyfile or the tunnel:

```bash
ss -tlnp | grep 8443                      # on the VPS: must show 10.78.0.1:8443, not *:8443
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://10.78.0.1:8443/bot123:invalid/getMe   # 401 from Telegram
curl -s -o /dev/null -w '%{http_code}\n' http://10.78.0.1:8443/                               # 404
docker exec mainserver-celery-worker-1 python -c "import os,django;\
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup();\
import json,urllib.request;from django.conf import settings;\
print(json.load(urllib.request.urlopen(f\"{settings.TELEGRAM_API_BASE_URL}/bot{settings.TELEGRAM_NOTIFY_BOT_TOKEN}/getMe\"))['ok'])"
```

`getMe` is the right probe: it proves the path end to end without delivering anything to a user.

The stack also watches the public site itself: blackbox-exporter probes `https://anicast.online/` and the titles API from the internet (`SiteDown` after 3 minutes, `SiteSlowWarning` above 3s), and a node-exporter on the VPS (`infra/monitoring/vps/compose.yml`, bound to `10.78.0.1:9100` on the AWG interface only — the VPS firewall is disabled) feeds host disk/memory rules for the public host. The nginx metrics sidecar resolves the backend per request, so scraping survives backend container recreation. Alertmanager groups by alert and severity, repeats after 4 hours and sends resolved notifications.

Secret files under `infra/monitoring/secrets/` (gitignored) are mounted read-only: `metrics-token` mirrors `METRICS_BEARER_TOKEN`, `telegram-token` and `telegram-chat-id` carry the ops bot credentials. After changing them, `docker compose -f infra/monitoring/compose.yml restart alertmanager`.

Every file holding a secret is `600`: the three `infra/*/.env` files and all of `infra/monitoring/secrets/`. `infra/vps/.env` (which carries `INTERNAL_API_TOKEN`) and the monitoring secrets were world-readable until 2026-09-04; only the `750` on `/home/lama_admin` stood between them and any other account on the host. Docker reads them as root, so the tighter mode costs nothing.

## Account mail

Password reset, address verification and the password-changed notice go out over SMTP with **no relay** — unlike Telegram. Measured from MainServer on 2026-09-04, from the host and from inside `mainserver-backend-1`: 587 and 465 connect and STARTTLS completes against Gmail, Yandex, Resend, Postmark and SES, while `api.telegram.org:443` still times out from the same container. So the block that forced the Telegram relay is specific to Telegram's address range, and account mail needs credentials, not a proxy.

Re-run the check before blaming mail configuration:

```bash
docker exec mainserver-backend-1 python -c "import smtplib,ssl;\
s=smtplib.SMTP('smtp.resend.com',587,timeout=15);s.ehlo('anicast.online');\
s.starttls(context=ssl.create_default_context());print(s.ehlo('anicast.online'));s.quit()"
```

Configuration lives in `infra/mainserver/.env` (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `ACCOUNT_LINK_TTL_SECONDS`). **`EMAIL_HOST` empty is a supported state, not an outage**: `/auth/password/reset/` and `/auth/email/verify/` answer 503 with a reason, no ledger row is written, and registration and login are unaffected. Never let those endpoints answer "check your inbox" without a transport — an unrecoverable account is the failure this whole feature exists to prevent.

Before switching a provider on, `anicast.online` needs SPF, DKIM and DMARC. As of 2026-09-04 the zone (`ns*.dnsowl.com`) has no `MX`, no `SPF`, no `_dmarc` and no DKIM selector, so mail from that domain lands in spam or is dropped outright. The provider issues the exact records; the `DEFAULT_FROM_EMAIL` address must be one it is authorised to send for.

The delivery shape mirrors Telegram notifications, and for the same reason:

- `accounts/mail.py` composes and sends one message, raising on failure. Nothing else touches SMTP.
- `accounts/tasks.dispatch_account_emails` owns the ledger and the retries: three attempts, then the row stays FAILED. Beat re-scans every 5 minutes, so a broker outage delays a reset link instead of losing it.
- `AccountEmail` is the ledger; the request path writes the row and only then enqueues (`enqueue_account_email`).
- PENDING rows older than an hour are closed as EXPIRED instead of being sent. A reset link that arrives after the person gave up is worse than none — they have already asked again.

**The link secret is minted inside the delivery attempt, not at request time.** `AccountEmail` holds no token, `AccountToken` holds only a SHA-256, so no usable link exists at rest and its lifetime starts when the mail actually goes out. Both tables are read-only in `/staff/`: re-sending from the admin would mint a second live link for one account.

Two orderings in the flow are load-bearing:

- A reset requested for an **unverified** address mails a verification link instead, with a byte-identical response. Registration accepted any address, so an account may hold one that was a typo or somebody else's; mailing a reset link there hands over the account. Opening a verification link then proves the mailbox, and the next request is a real reset. Confirming a link also verifies the address for the same reason.
- Verification proves *the address the link was sent to*, not whatever the account holds when it is opened (`AccountToken.email`). Otherwise requesting a link and then changing the address would confirm the new one with nobody ever reading mail there.

A reset ends **every** session for that account, since it is the remedy for a compromise and a 30-day rolling cookie would otherwise keep the attacker signed in for another month. A password change ends every *other* session, keeps the caller signed in (`update_session_auth_hash`) and deletes any pending reset token, so an older mailbox capture cannot undo it. `/auth/sessions/revoke/` does the same without changing the password, and that is the case where row deletion is the whole mechanism: Django already rejects sessions whose password-derived hash no longer matches, so after a password change the other devices are unauthenticated regardless — deleting the rows makes the reported count truthful and drops the leftover data. Finding a user's sessions means walking unexpired rows and decoding each, since sessions are opaque; acceptable only because these are explicit, throttled actions.

Existing accounts are **not** backfilled as verified: nobody checked those addresses, and the reset flow already handles the state. `anicast_account_emails_total{result="failed"}` drives `AccountEmailFailures` (critical after one failure in an hour, unlike Telegram pushes where a blocked bot is routine) because the failure mode here is silence: the person sees "check your inbox" and nothing arrives.

Enqueueing runs on the user's request path, so Kombu's retry policy is capped at 2 quick attempts (`CELERY_TASK_PUBLISH_RETRY_POLICY`). The default 20 retries at one-second intervals turned "Redis is down" into a 20-second wait on registration and password reset before the identical beat fallback ran — measured at 19.0 s, now 0.27 s. The worker keeps `broker_connection_retry_on_startup`, since nothing is waiting on it.

## Catalog search

Search is by fragment (`ILIKE '%нару%'`), which no B-tree can serve. Two pieces make it indexable and both are required:

- `pg_trgm` GIN indexes on `UPPER(column::text)` for every searched name field (migration `catalog.0019`). The expression matters: Django compiles `icontains` to `UPPER(name::text) LIKE UPPER('%…%')`, so an index on the bare column is never consulted — verified on the production dump, where raw-column indexes left the query scanning all three tables in 31ms.
- The query shape in `catalog/search.py`. `Q(name__icontains=q) | Q(translations__name__icontains=q)` becomes a JOIN with an OR across two tables, which Postgres cannot serve from per-table indexes. Matching ids are collected as a `UNION` of one indexed subquery per field instead.

Measured on the production dump, character search (7007 rows, 13986 translations) with a 3+ character term: 14.3ms → 1.5ms. Scaled to 70070 characters: 80ms unindexed, 10ms indexed.

**Two-character terms are not indexed and cannot be.** A trigram needs three characters, so `%lu%` yields none and the planner scans — 83ms at 70k rows. `min_query_length` is 2 because two characters are a meaningful query in Japanese, so the shortest allowed term is exactly the case the index misses. The `s-maxage=300` response cache covers it. If that becomes the bottleneck, the options are a prefix index or a three-character minimum, not a different trigram setting.

These indexes are created as raw SQL behind a vendor guard, not as `Meta.indexes`: `GinIndex(OpClass(Upper(...)))` raises `OperationalError` when SQLite applies it, and the test database is SQLite. The consequence is that they are invisible to Django's model state, so `makemigrations` cannot detect drift on them. If you drop one, drop it in the migration.

## Taking user content down

Clearing `is_active` on the account in `/staff/` is the takedown mechanism. It blocks sign-in, hides the public profile, blocks following, withdraws approved reviews from every title page and the community feed, and makes public collections answer 404. Nothing is deleted, so it is reversible.

That reach is deliberate and enforced in one place each: `community.views.published_reviews` filters `user__is_active`, and `PublicCollectionDetailView` filters `owner__is_active`. Before those filters existed, deactivation hid the profile while leaving the reviews and collections readable — a takedown that looked complete and was not. Any new endpoint that publishes user-authored content has to apply the same filter.

Public review payloads carry `author_name` verbatim, including empty, and the client substitutes a localized placeholder. Do not reintroduce a server-side fallback built from account fields: the previous one embedded the internal primary key, which exposed registration order and a rough user count for precisely the authors whose `public_id` is withheld because their profile is private.

## Staff dashboard cost

`/staff/` renders attention cards plus a status-page availability section, and everything on it must stay bounded — an editor loads it constantly, and it shares the request path with the public API.

`common.availability.summarize` computes its rolling windows with aggregates (`Count`/`Avg`/`Min`/`Max` with `filter`), not by loading rows. It used to read the whole 7-day window into Python: at minute resolution that is ~13k rows per target and ~39k per render, to produce a handful of percentages. Measured on production data, the dashboard went from 0.94 s to 0.065–0.082 s warm; the first render after a restart is ~0.7 s because those index and heap pages come from disk. A query-budget test asserts the count does not grow when the history doubles.

`_poster_tier_counts` deliberately still classifies filenames in Python: measured at 0.16 s over two queries, and the SQL alternative is five unindexed `LIKE` scans plus a second copy of the poster filename grammar. Do not "optimize" it without a measurement showing the current version is the bottleneck.

## Image publication

Prefer CI (`.github/workflows/publish.yml`) and immutable registry digests.
Production release scripts now default to the live project names `mainserver`
and `vps`; there is no project-name migration to perform.

For a local build, pass both public Telegram bot build arguments (read the current
configuration, never assume names), keep CPU/memory constrained, save/load the image
to the VPS and address it by its exact `sha256:<64 hex>` image ID. Use
`ANICAST_LOCAL_IMAGES=1` with deploy/rollback; this explicitly skips registry pulls.
Mutable tags are no longer accepted by deploy.sh. GHCR push permissions and CI
publication should be verified before claiming a registry release.

Do not run an unconstrained production build on MainServer while it serves traffic.
The host has limited RAM/CPU; prefer CI or a separate builder. A local maintenance
build must use low CPU/I/O priority and preserve the running application.

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

## Caching and image delivery

Public catalog GETs carry `Cache-Control: public, max-age=0, s-maxage=60, stale-while-revalidate=300` (search: `s-maxage=300`, since it runs three unindexed ILIKE scans per request) plus `Vary: Accept, Accept-Language, Cookie`. The `Vary` is the load-bearing half: payloads are localized from `?lang=`, the `anicast_lang` cookie and `Accept-Language`, so a shared cache that ignored those would serve one visitor's language to another. `max-age=0` keeps browsers revalidating while allowing an intermediary to serve within the window.

Authenticated responses are deliberately never marked cacheable, and playback endpoints keep `no-store, private`. Both are covered by tests, because the failure mode of getting this wrong is serving one session's data to another.

Images go through the Next optimizer, which caches variants in `.next/cache/images` keyed by source URL and parameters. The `vps_frontend_images` Docker volume now preserves this directory across releases. It contains optimized public images only, not HTML or user API responses. Monitor disk consumption. Two settings matter:

- `formats: ["image/webp"]`. Without it Next negotiates nothing and a browser advertising WebP still received the original PNG/JPEG. AVIF is **not** listed on purpose: measured on the production VPS (1 vCPU) with a real 6.2 MB poster at quality 92, WebP is 88.6 KB in 1.9 s while AVIF is 122.1 KB in 6.8 s. At this quality AVIF is both larger and 3.5x slower, and Next would negotiate it first. Revisit only with a fresh measurement at a lower AVIF-specific quality.
- `minimumCacheTTL` of 30 days. Poster filenames are content-addressed (a SHA-256 prefix), so a URL never changes meaning and a long TTL cannot serve stale art. The 60-second default re-encoded the same posters all day; a cold miss costs up to 4 s through the tunnel, a hit about 0.5 s.

Edge caching for `/api/v1/media/*` was considered and rejected on measurement. Over a 56-minute window at the edge, media was 16 of 691 requests with a repeat ratio of 1.0 — not a single URL fetched twice — at p95 0.55s. A cache with nothing to hit would buy a custom Caddy build and its supply chain for no gain, and Django already answers `public, max-age=31536000, immutable`, so browsers refetch nothing on repeat visits.

What the earlier measurement actually found was crawler load: 46% of edge requests came from backlink and keyword crawlers (MJ12bot alone 35%), and every poster byte they pulled crossed the tunnel. `frontend/app/robots.ts` now denies that group the media path only — they keep HTML, links and metadata, so the site still appears in Ahrefs/Semrush reports, and search engines are untouched. Revisit an edge cache if the repeat ratio rises; that ratio is the number that decides it, not the absolute request count.

**HTTP/3 cannot be enabled on this host.** AmneziaWG listens on UDP/443 (`ListenPort = 443` in `/etc/amnezia/amneziawg/awg0.conf`) to disguise tunnel traffic as QUIC. Caddy's h3 listener therefore fails with `bind: address already in use`, and Caddy treats that as a fatal config error: the container restart-loops and the whole site goes down, not just h3. This was verified in production on 2026-09-03 — the site was unreachable for roughly two minutes until `protocols h1 h2` was restored. Enabling h3 requires moving the tunnel off 443 first, which trades its DPI camouflage for a protocol upgrade; on a network that already blocks Telegram egress from this host, that camouflage is doing real work. Do not re-add `h3` without changing the tunnel port and re-testing.

## Response headers and CSP

`infra/vps/Caddyfile` sends the site's security headers. The policy is anchored on `default-src 'self'`; before that was added, only `img-src` and `frame-src` were set, so `script-src`, `connect-src`, `object-src` and `base-uri` fell back to unrestricted and an injected `<script src>` from any origin would have run.

Each exception is measured against the live HTML, not assumed:

- `script-src 'self' 'unsafe-inline'` — the App Router streams its bootstrap and RSC payloads through inline `<script>` tags (32 on the home page) plus the JSON-LD blocks. Nonces would require `headers()` per request, which opts every page out of static rendering — a real cost for a catalog whose value is cacheable HTML. Read this honestly: the directive stops remote script injection, not a successful inline XSS.
- `style-src 'self' 'unsafe-inline'` — React inline `style` attributes (progress bars, genre shares; 29 on the home page) are `style-src-attr`. CSS Modules themselves are files.
- `connect-src 'self'` — the frontend calls only its own `/api/*`, which Caddy proxies. Verified: no third-party fetch target anywhere in `frontend/`.
- `font-src 'self'` — fonts are system stacks (`ui-sans-serif, system-ui, …`), no webfont is loaded.
- `frame-src 'self' https://kodikplayer.com` — the only embed, matching the provider's `allowed_hosts`. The iframe also carries `sandbox` and `referrerPolicy="no-referrer"`.
- `object-src 'none'`, `base-uri 'none'`, `form-action 'self'` — nothing on the site uses `<object>`/`<embed>` or a `<base>` tag, and every form posts to its own origin.

`frame-ancestors 'none'` is what actually prevents framing in current browsers; `X-Frame-Options` stays for older ones and now says `DENY`. It previously said `SAMEORIGIN` here while Django sent `DENY` on `/api` and `/staff`, so the two layers disagreed about the same site. Validate after editing: `docker run --rm -v "$PWD/infra/vps/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile`.

Recovery pages are excluded from crawling in two independent places, because they carry a single-use token in the query string. `frontend/next.config.ts` adds `X-Robots-Tag: noindex` to `/forgot-password`, `/reset-password` and `/verify-email`, and `frontend/app/robots.ts` additionally *disallows* the two token paths. The `Disallow` is the one that matters: `noindex` only takes effect after the URL is fetched, and fetching is the harm — a crawler following a leaked reset link spends it before the person opens their mail.

## Title detail and episode pages

`/api/v1/titles/<slug>/` always paginates the embedded episode list (`episodes_page`, `episodes_page_size`, default 20, max 50) and reports the total in `episodes_count`. Pagination is not opt-in: a request without parameters — a crawler, a curl probe, an older client — would otherwise serialize the whole series, and One Piece alone is 1180 episodes with 4236 sources. Cast lists are bounded the same way through `characters_page` / `characters_count`. `episode_sources=0` is the opt-in compact mode used by the title UI: episode rows omit playback sources and avoid their queries; the dedicated episode endpoint still returns playback-gated sources. Metadata additionally requests one episode and one character with a 60-second revalidation window.

`GET /collections/` returns cards, not contents: `item_count` plus `preview_items` (the first four positions, poster and name only). The nested title payload stays on the detail endpoints, where a collection is capped at 200 items and every one is rendered. At the project ceilings (50 collections × 200 items) the previous shape was a 3.6 MB response built to draw a few posters per card; it is now 30 KB. The title page asks `GET /collections/?title=<slug>`, which fills `contains_title` server-side instead of shipping every collection's item list to compute membership in the browser.

DRF is configured with a default pagination class and page size. Every current list view declares its own, so nothing changes today; the default exists so the next `ListAPIView` cannot ship unbounded by omission. Opting out must stay explicit (`pagination_class = None`).

All server-side Next.js request paths, including public profiles and collections, use `INTERNAL_API_BASE_URL` over AWG and send `X-AniCast-Internal-Token`. Store the same random value (at least 32 characters) as `INTERNAL_API_TOKEN` on MainServer and VPS. Caddy strips that header from every public `/api/*` request. Valid safe internal requests use the separate `ssr=600/min` bucket; public anonymous traffic remains at `60/min`, and frontend retry is limited to transport failures only.

Every header-secret comparison (`INTERNAL_API_TOKEN`, `METRICS_BEARER_TOKEN`, both Telegram webhook secrets) goes through `common.security.constant_time_equals`. Django decodes request headers as latin-1, so a client can send code points 128–255; `hmac.compare_digest` raises `TypeError` on non-ASCII `str`, which on the default throttle path would have turned one hostile header into a 500 on every API request. Comparing bytes keeps a hostile header an ordinary mismatch, and an unset secret fails closed.

Throttling is layered. Anonymous traffic uses `anon=60/min` per address, authenticated traffic `user=240/min` per account (DRF's `AnonRateThrottle` skips logged-in requests, so without the user bucket one cheap account could hammer account summary, recommendations and continue-watching without limit), trusted SSR `ssr=600/min`, login `auth=10/min` per address, registration `register=20/hour` per address, account mail `account_mail=10/hour` per target address, playback `playback=30/min`. `DJANGO_NUM_PROXIES` (default 1) matters here: exactly one trusted proxy sits in front, and without it DRF keys buckets on the whole `X-Forwarded-For`, so a client-supplied prefix would mint a fresh bucket per request and defeat every limit.

Registration gets its own, much tighter bucket because it answers a question login refuses to. Login is deliberately generic ("wrong email or password"), but registration has to tell a returning user their address is taken — silently attaching a second registration to someone else's account would be worse than the disclosure — which makes it an account-enumeration oracle. Sharing login's per-minute budget allowed roughly 14k probes a day from one address; a person registering once never notices an hourly limit.

`account_mail` is keyed on the **target address**, not the caller, because the cost of abuse falls on the mailbox owner and a botnet has many addresses while the victim has one inbox. The key is the SHA-256 of the address: throttle keys share the Redis instance with the cache, so raw keys would let anything that can read Redis enumerate which addresses were tried. A throttled reset request is indistinguishable from an accepted one.

All AniCast throttles mix in `common.throttling.LiveRatesMixin`. DRF binds `THROTTLE_RATES` to the class body at import time, so a settings override never reaches it: a changed rate looks applied while the old value is still enforced, and any test asserting on a limit silently asserts on the default instead. Keep the mixin on new throttle classes.

The visit counter (`/api/v1/analytics/visit/`) is a plain Django view outside the DRF defaults, and both of its own guards are advisory: the bot check reads the User-Agent and the dedupe check reads a cookie the client controls. Only the counting branch is throttled at `visit=600/hour` per address, so returning browsers with their signed cookie never spend the budget, and a cookie-less script can no longer take a row lock on today's counter per request. Exhausting the bucket stops counting and still answers 200 — it never fails a page load for a vanity metric.

Gunicorn runs 2 workers × 2 threads with `--timeout 30`, `--graceful-timeout 30`, `--keep-alive 5` and request recycling at 2000 (±200 jitter). The default single sync worker meant one slow request blocked the whole API including the container healthcheck. The timeout sits above the frontend's 10-second fetch budget so gunicorn never kills a request the client still awaits. With `CONN_MAX_AGE=60` (`DJANGO_CONN_MAX_AGE`) and `CONN_HEALTH_CHECKS`, persistent connections stay bounded at 4 per backend container. Access logging stays off: `ObservabilityMiddleware` already emits one structured JSON line per request, and gunicorn's plain-text log would mix two formats into the same stdout stream.

## Dependency pins

`backend/requirements.txt` holds the 15 direct dependencies; `backend/constraints.txt` holds the 52 transitive ones, generated from the exact set the production image installs. Regenerate it from a freshly built image after changing requirements:

```bash
docker exec mainserver-backend-1 pip freeze     # keep only entries absent from requirements.txt
docker build backend && docker run --rm <image> pip freeze | diff - <expected>   # must be identical
```

Do not pin a direct dependency in both files: pip resolves the conflict in favour of the constraint, so the two would disagree silently.

The pins are for reproducibility, not for the audit. `pip-audit --requirement` resolves the whole dependency graph rather than only the named pins — verified: a file containing just `requests==2.34.2` audits `urllib3`, `idna`, `certifi` and `charset-normalizer` as well, and the full run reports 66 packages against 15 direct pins. What the empty constraints file actually cost was determinism: a rebuild could pick up any newer transitive release, so an image built today could differ from the one the suite passed on. Verified after generating it — a fresh `docker build backend` produces a package set byte-identical to the tested one.

The metrics endpoint aggregates 24-hour availability in bounded SQL and groups provider/source counts. Keep this path bounded: Prometheus scrapes every 30 seconds and a full Python scan of raw probe history would block a request-serving worker.

## VPS firewall

Verified 2026-09-08: `ufw status` returns **inactive**. An earlier version of this
runbook incorrectly described it as enabled. Service-level private binding is
currently essential. Before enabling a firewall, inventory public SSH, TCP 80/443,
AWG UDP 443, tunnel routing/NAT, metrics and the Telegram relay, and retain a
separate public-SSH recovery connection. Do not change AWG UDP/443 casually.

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

MainServer verification requires PostgreSQL, Redis, Django readiness, both Celery workers (`celery-worker` and `celery-bulk`) and Celery Beat health. The notification/default worker and bulk worker each run with concurrency 1; allow up to 600 seconds for warm shutdown of running tasks. VPS verification requires frontend and Caddy health plus a loopback frontend request. Run public smoke separately after both stacks pass:

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

## Release state and bootstrap

Before the first deploy, create `<state-dir>/current.env` from the **actually running**
image ID/digest and the absolute production env-file path. `deploy.sh` refuses to
proceed without that rollback baseline. State directories are private; manifests
contain image IDs, release identifiers and paths, never secrets.

Example for a local-image release, after loading the tested image:

```bash
ANICAST_LOCAL_IMAGES=1 scripts/deploy.sh mainserver /tmp/mainserver-release.env /var/lib/anicast/releases/mainserver
# On the VPS, from /opt/anicast:
ANICAST_LOCAL_IMAGES=1 scripts/deploy.sh vps /tmp/vps-release.env /var/lib/anicast/releases/vps
```

`ANICAST_PROJECT_MAINSERVER` and `ANICAST_PROJECT_VPS` remain available for deliberate
alternative environments; the defaults match production. Keep the release state
and the operator-facing env image selection synchronized after a successful release
to avoid a later manual compose invocation reviving an older tag.

Before changing Compose topology, copy the currently running Compose file as well
as image identifiers. The image-only rollback script uses the checked-out Compose
configuration; restore the captured configuration separately when undoing topology.
Never restore a database automatically to roll back application code.

The 2026-09-08 rollout and actual checks are recorded in `RELEASE-2026-09-08.md`.

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
