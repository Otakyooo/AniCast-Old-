---
name: anicast-ops
description: Audit or operate Anicast Docker services, deploy immutable releases, diagnose resources and verify encrypted backups or isolated recovery on MainServer and VPS. Use for runtime and release work, not ordinary application-only edits.
---

# Anicast operations

Start with [current state](../../../docs/IMPLEMENTATION_STATUS.md), then read only
the needed runbook: [deployment](../../../docs/operations/DEPLOYMENT.md),
[monitoring/Redis/firewall](../../../docs/operations/MONITORING.md) or
[backups/recovery/migration](../../../docs/operations/BACKUPS.md).
[Archive](../../../docs/archive/README.md) contains dated evidence, not live settings.

Production project names are `mainserver` and `vps`; changing them creates different
volumes. MainServer checkout is `/home/lama_admin/anicast`; VPS `/opt/anicast` has
no git. Reach VPS through MainServer at `10.78.0.1`; nested SSH in batches needs
`ssh -n` so it cannot consume subsequent commands from stdin.

Before rollout record actual image IDs, git status, Compose and private env paths
without printing values. Use a successful CI release artifact and immutable env
snapshot; never overwrite a snapshot referenced by current/previous manifests.
No builds on the small VPS. Confirm a real rollback baseline before deployment.
Image rollback changes neither Compose topology nor production database contents.

MainServer has three Redis roles: broker/results, control and ephemeral. Former
broker DB 2 is stale migration evidence, not an automatic control rollback target.
Check both Celery workers separately; one pong does not prove two workers work.
Preserve queues and allow warm shutdown: 600s default worker, 1900s bulk (longest
task hard limit 1800s). Deploy and rollback share `scripts/start-release.sh`: API
readiness must pass before default/beat and then bulk are updated. Never replace
this with one full-stack `compose up` that delays API startup behind worker drain.

Check readiness, every configured healthcheck, public home/titles API and public
404 for `/internal/metrics`. UI changes need real browser verification. Firewall
changes also need a fresh frontend-container request to the public HTTPS origin;
cached posters hide Docker hairpin failures. Never flush the global nft ruleset.
UDP/443 belongs to AWG; enabling Caddy HTTP/3 there conflicts with the tunnel.

Use `scripts/capacity-report.py --hours 24` and a recent 1h window before changing
limits. Measure installed RAM/CPU: a future RAM upgrade is not current capacity
and does not imply more CPU. Active swap, available RAM and latency matter together.

Manual backup checks use BACKUP_NOTIFY=0. Recovery drills use unique disposable
resources, captured Telegram and in-memory email, not real messages. Preserve the
restore script's memory guard. Update both encrypted kits after OAuth/runtime
changes and verify them from the operator computer; the decryption identity never
goes to servers. Report actual checks, remaining risks and commit/push/deploy state.
