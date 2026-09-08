---
name: anicast-ops
description: Audit, deploy or troubleshoot Anicast Docker services on MainServer and the public VPS, including release manifests, health checks and queue isolation. Use for Anicast runtime and release work, not unrelated servers.
---

# Anicast operations

Read `docs/OPERATIONS.md` and the latest `docs/RELEASE-*.md` for actual state.
For architecture decisions read `docs/architecture/001-stability-first.md`.

The production Compose names are `mainserver` and `vps`; the same names own the
existing database and media volumes. MainServer repo is `/home/lama_admin/anicast`;
VPS files are `/opt/anicast` and may not include git. SSH to the VPS through the
MainServer uses `10.78.0.1`; use `ssh -n` in noninteractive command batches so a
nested SSH process cannot consume subsequent commands from stdin.

Before a release record live image IDs, git diff/status, Compose files and private
env-file paths without printing secrets. Bootstrap current.env from the actual
running image, not the expected tag. Registry digests are preferred; transferred
local images require `ANICAST_LOCAL_IMAGES=1` and an exact sha256 image ID.

Check both Celery workers separately. `celery-worker` consumes default and
notifications; `celery-bulk` consumes providers/posters/maintenance/analytics.
A generic inspect ping that receives one pong is not proof both workers work.
Never purge queues to resolve a deployment delay; allow warm shutdown.

Build/check before changing services. Run `scripts/validate.sh` for infrastructure.
Use the successful CI `release-<sha>` artifact for registry deployments; add only
the host's immutable private ANICAST_ENV_FILE snapshot. Do not build on the VPS
or overwrite an env snapshot used by current/previous releases. See ADR 004.
For isolated recovery use `scripts/restore-isolated.py` and the recovery runbook;
preserve its memory guard, unique resources and separation from production data.
After deployment require container health, backend readiness, the public home and
titles API, and a public 404 for `/internal/metrics`. For UI changes verify a
real browser as well. Do not expose `/health` or metrics through Caddy.

Image rollback does not undo Compose edits or DB migrations. Restore the captured
Compose file when reverting a topology change; keep DB migrations expand/contract.
Use the existing backup/restore runbook for data operations, only within the user's
authorization. Do not run a production restore as a release smoke test.

Record evidence, remaining risks, and whether a commit was pushed. Do not describe
an unrun check, an unverified offsite backup or a prepared release as successful.

Three Redis roles now exist: broker, control and ephemeral. A topology rollback
must keep the authoritative control state; stale DB 2 on the broker is not an
automatic rollback target. Use ADR 005 for the migration and RPO/RTO contract.
After firewall changes, test a fresh request from the frontend container to the
public HTTPS origin: Docker hairpin traffic enters through a bridge, not eth0.
Cached posters and successful external requests do not prove that path works.

Recovery credentials are encrypted to an offline recipient. Test from the
operator's computer without MainServer and refresh both host kits after OAuth or
runtime changes. Manual backup checks use BACKUP_NOTIFY=0. Read/write drills use
only disposable restore resources; email stays in memory and Telegram uses a
capture sink. Do not label these checks real external message delivery.
