# Deployment

[Эксплуатация](../OPERATIONS.md). Команды выполняются из корня репозитория, если не указано иначе.

## Release manifests

The primary path is the successful `publish` workflow in GitHub Actions. It calls
all CI gates before publishing linux/amd64 application images to GHCR, then uploads
`release-<full-git-sha>` with mainserver.env, vps.env and release.json (90-day artifact
retention). Download that artifact for the chosen successful run, retain it with
the release records, and add ANICAST_ENV_FILE pointing to an immutable private
runtime snapshot on each host. Do not build on production or deploy a moving tag.
The artifact is not an automatic production deployment and contains no secrets.

Current registry rollout and measured recovery evidence:
[release 09.09](../archive/releases/RELEASE-2026-09-09-registry.md), [ADR 004](../architecture/004-registry-and-recovery.md).

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

MainServer verification requires PostgreSQL, all three Redis services, Django readiness, both Celery workers (`celery-worker` and `celery-bulk`) and Celery Beat health. The notification/default worker and bulk worker each run with concurrency 1; allow up to 600 seconds for warm shutdown of running tasks. VPS verification requires frontend and Caddy health plus a loopback frontend request. Run public smoke separately after both stacks pass:

```bash
curl --fail --silent --show-error --max-time 15 https://anicast.online/ >/dev/null
curl --fail --silent --show-error --max-time 15 \
  'https://anicast.online/api/v1/titles/?page_size=1' >/dev/null
test "$(curl -sS -o /dev/null -w '%{http_code}' https://anicast.online/internal/metrics)" != 200
```

Before MainServer deployment, create and verify a PostgreSQL logical backup according to the existing host backup policy. The deploy script intentionally does not claim to implement backup retention or restore verification.


## Automatic rollback

Any failed Compose health or smoke gate triggers `scripts/rollback.sh` for that stack and verifies the previous manifest with the same probes.

The script also accepts a retained local SHA baseline during the transition from
local images: it inspects the image locally and skips registry pull. Keep the
previous image and its env snapshot until the release is no longer needed.

Manual rollback is:

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
npm run audit
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

`scripts/validate.sh` runs shell syntax checks, Compose config validations for all three stacks, promtool/amtool checks of the monitoring configuration with placeholder secrets, the hermetic deploy/rollback test and rejects public metrics routes in Caddy. CI additionally builds both images and validates Caddy with the official image.

Frontend CI runs `npm run audit` against production and development dependencies;
high/critical advisories fail the job. The infrastructure job also executes a
PNG-to-WebP resize inside the final musl image with networking disabled, proving
that the packaged sharp/libvips runtime works after dependency changes.

`pip-audit` is part of the pinned requirements and gates CI. Pinned dependencies go stale silently, so a missed security release must fail the build instead of waiting to be discovered: the audit is what turns the pins into a maintained set rather than a snapshot. `DJANGO_SECRET_KEY` has no safe fallback in a non-SQLite deployment — the placeholder key signs sessions, the visit cookie and playback tokens, and the guard fires regardless of `DJANGO_DEBUG` so a stack accidentally booted with debug on cannot run on a publicly known key.
