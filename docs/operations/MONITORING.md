# Monitoring

[Эксплуатация](../OPERATIONS.md). Команды выполняются из корня репозитория, если не указано иначе.

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

There are three Redis services on MainServer; the VPS has none.

- `redis` remains persistent (AOF), `noeviction`, 200 MiB maxmemory / 256 MiB
  container limit. `CELERY_BROKER_URL` uses DB 0, `CELERY_RESULT_BACKEND` DB 1;
  both use `REDIS_PASSWORD`. Former control DB 2 is retained as migration evidence,
  not used by current clients and not an automatic rollback target.
- `redis-control` is persistent (AOF), `noeviction`, 64 MiB maxmemory / 96 MiB
  container limit. `CONTROL_CACHE_URL` points to DB 0 with its separate
  `CONTROL_REDIS_PASSWORD`; this is the authoritative coordination state.
  Canonical: `redis://:***@redis-control:6379/0` (see `infra/mainserver/env.example`).
  A stale broker DB 2 entry must never be reintroduced: it revives obsolete
  locks/cursors after an image-only rollback.
- `redis-cache` is disposable: `allkeys-lru`, 64 MiB maxmemory / 96 MiB container
  limit, no AOF/RDB. `CACHE_URL` points to DB 0 here with the separate
  `CACHE_REDIS_PASSWORD`. It has no host port and is not on the metrics network.
- Django alias `default` is CONTROL_CACHE_URL: throttles, locks, provider cursors.
  Alias `ephemeral` is CACHE_URL: optional counters, and future disposable data.
  Never use `ephemeral` for locks, rate limits or sessions. Sessions remain in DB.
- Older env files without CONTROL_CACHE_URL fall back to CACHE_URL for both
  aliases. This preserves compatibility but does not provide isolation.

Keep credentials out of logs. Healthchecks use REDISCLI_AUTH. Rotate a password
in the server setting and every URL referring to that server, then recreate its
clients with the same Compose project name. A cache password is not a broker
password. No Redis service is exposed through a host port.

Cache failures skip telemetry with a five-second per-process retry pause and
bounded socket timeouts. Readiness tests the mandatory coordination cache;
disposable cache downtime does not make the API unready. Deploy still requires
all three Redis services to be healthy. Counters reset after cache loss/eviction;
Prometheus keeps previously scraped history. DB-derived gauges remain available.
Fresh metrics `anicast_redis_up`, `anicast_redis_used_memory_bytes`,
`anicast_redis_maxmemory_bytes`, and `anicast_redis_evicted_keys_total` distinguish
broker, control and ephemeral roles. Alerts cover unreachable Redis roles and persistent
memory above 80%; these probes never depend on the counter cache.

See [ADR 005](../architecture/005-control-and-offline-recovery.md) for current
rollout/rollback; ADR 002 describes the earlier cache split. Keep runtime env
snapshots immutable. Image rollback must preserve the authoritative control URL:
returning to stale broker DB 2 can revive obsolete locks/cursors. Current and
baseline rollback manifests use compatible private snapshots; never overwrite them.

Key signals:

- `anicast_http_requests_total` and `anicast_http_request_duration_seconds`;
- `anicast_celery_tasks_total`;
- `anicast_source_checks_total` and `anicast_source_check_duration_seconds`;
- `anicast_notification_deliveries_total`;
- `anicast_providers` and `anicast_sources`.

Alert at minimum on repeated backend readiness failures, HTTP 5xx increase, provider check failures, Celery task failures, notification failures, unhealthy Compose services, stale AWG handshake, disk pressure and missing backups.


## Monitoring stack

`infra/monitoring/compose.yml` runs on MainServer as a separate Compose project joined to the external `mainserver_metrics` network:

- Prometheus (retention 15d, `127.0.0.1:9090`) scrapes the backend through the nginx sidecar, which adds the `X-Forwarded-Proto: https` header Django requires and keeps the bearer token flow intact;
- Alertmanager (`127.0.0.1:9093`) delivers alerts with the native Telegram receiver;
- node-exporter provides host disk, memory and CPU metrics;
- every service is memory-limited; the whole stack uses roughly 110 MiB.

### Capacity history on small hosts

Run `python3 scripts/capacity-report.py --hours 24` on MainServer. This reads the
existing private Prometheus over loopback and prints aggregate JSON for MainServer
and VPS: available/total RAM, CPU busy and I/O wait, active swap-in/out rates and
exporter availability. It installs no service, sends no messages and changes no
runtime configuration. Use `--hours 1` to focus on the recent release; 72h is the
maximum to bound query cost. Exit 1 means a query failed; exit 2 means at least one
signal has no finite data. Partial coverage is printed explicitly, even on exit 0.

Samples are five minutes apart and CPU/swap use five-minute averages. Coverage
describes the presence of sampled history, not service uptime. Missing data is not
zero load; check `scrape_up` before interpreting other signals. A historical maximum
can include builds, deployments and restore drills. Compare one-hour and daily
windows before changing resources; neither this report nor a short idle snapshot
establishes a supported number of concurrent visitors.

MainServer RAM was increased on 09.09.2026 and the OS now sees 3606 MiB; CPU
remains one. Retain current limits and concurrency 1 for each Celery worker
until `scripts/capacity-report.py --hours 24` plus a `--hours 1` window justify
a change. No CPU expansion has been confirmed. Investigate sustained low
available RAM together with active swap and response latency; occupied swap
alone is not a reason to restart services. Additional RAM provides headroom
but does not remove the home host/network failure dependency. CPU busy
includes I/O wait, which is reported separately.

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

The stack also watches the public site itself: blackbox-exporter probes `https://anicast.online/` and the titles API from the internet (`SiteDown` after 3 minutes, `SiteSlowWarning` above 3s). Probes originate on MainServer and cross the AWG tunnel, so a tunnel/firewall fault reads as `SiteDown` while the site stays reachable directly (incident 12.09.2026): confirm the tunnel before declaring the site down. A node-exporter on the VPS (`infra/monitoring/vps/compose.yml`, bound to `10.78.0.1:9100` on the AWG interface only — the Anicast firewall permits only MainServer on awg0) feeds host disk/memory rules for the public host. The nginx metrics sidecar resolves the backend per request, so scraping survives backend container recreation. Alertmanager groups by alert and severity, repeats after 4 hours and sends resolved notifications.

Secret files under `infra/monitoring/secrets/` (gitignored) are mounted read-only: `metrics-token` mirrors `METRICS_BEARER_TOKEN`, `telegram-token` and `telegram-chat-id` carry the ops bot credentials. After changing them, `docker compose -f infra/monitoring/compose.yml restart alertmanager`.

Application `.env` files remain `600`. Bind-mounted monitoring token files need
`640` with group **65534**, the GID of `nobody` inside the current Prometheus and
Alertmanager images. Docker mounting a file as root does not grant its non-root
reader permission: `600 lama_admin:lama_admin` caused live scrapes to fail with
permission denied. Preserve the deployment owner, grant read only to the container
group, and verify the actual UID/GID again when changing images. Do not make token
files world-readable. After changes run `sh scripts/verify-monitoring.sh` once a
scrape interval has elapsed; this checks file access and real samples, not only
container health. It sends no test notifications.


## VPS firewall

Enabled 2026-09-09: `anicast-firewall.service` owns `inet anicast_edge`.
UFW remains masked/inactive; its status is not the state of this firewall.
Public eth0 accepts TCP 22/80/443 and UDP 443. awg0 accepts MainServer
10.78.0.2 only for SSH, relay and exporter. The FORWARD hook runs before Docker
filtering: only the explicit exporter DNAT is allowed from the peer, while the
existing peer-to-eth0 egress path is preserved. Docker/AWG NAT rules are unchanged.

Source: `infra/vps/firewall.nft`; installed `/etc/anicast/firewall.nft`.
`systemctl reload anicast-firewall` applies an atomic replacement of the owned
table; never use a global nft flush ruleset. `scripts/verify-vps-firewall.sh`
checks local service/table state. Also verify fresh public/tunnel SSH, public
home/API, MainServer exporter/relay, and Prometheus node-vps samples after changes.
Retain a timed rollback until these checks pass. Full policy, installation and
rollback: [ADR 003](../architecture/003-vps-firewall.md), [release](../archive/releases/RELEASE-2026-09-09-firewall.md).
