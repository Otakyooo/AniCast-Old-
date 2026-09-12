# Backups

[Эксплуатация](../OPERATIONS.md). Команды выполняются из корня репозитория, если не указано иначе.

## Backups

`scripts/backup-db.sh` creates a verified `pg_dump -Fc` dump in `~/anicast/backups/db/` under `umask 077`, proves its table of contents readable with `pg_restore --list` (headers only — data blocks are proven by the weekly `restore-db.sh --verify` and the isolated drill, not by this check), applies retention (all dumps for 14 days plus Sunday dumps for 60 days; manual `predeploy-*` dumps are never removed) and copies the dump to an encrypted Google Drive remote (`rclone crypt` on top of the user-owned `AniCast Backups` folder). On any failure the script sends a Telegram message through the ops bot configured in `infra/monitoring/.env` and exits non-zero.

`scripts/backup-posters.sh` does the same for the shared artwork volume (`mainserver_poster_media`): a verified tarball in `~/anicast/backups/posters/` with 30-day local retention and an offsite copy on the same encrypted remote. Verification runs in a disposable `alpine:3.20` helper (96m, 0.4 CPU, no network), comparing file list against the archive. It contains title posters and mirrored character/creator portraits. Scheduled daily at 03:45 UTC; the pipeline can rebuild missing files from private origins, but a backup restores them without upstream traffic.

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

Cron on MainServer runs the backups and verifications (logs in `~/anicast/backups/backup.log`, `restore-verify.log` and `maintenance.log` for the prune job):

```cron
15 */6 * * *  ~/anicast/scripts/backup-db.sh >> ~/anicast/backups/backup.log 2>&1
45 3 * * *  ~/anicast/scripts/backup-posters.sh >> ~/anicast/backups/backup.log 2>&1
5 5 * * 0  sh ~/anicast/scripts/backup-recovery-kit.sh >> ~/anicast/backups/backup.log 2>&1
*/5 * * * *  python3 ~/anicast/scripts/backup-metrics.py >> ~/anicast/backups/backup.log 2>&1
30 4 * * 0  ~/anicast/scripts/restore-db.sh --verify >> ~/anicast/backups/restore-verify.log 2>&1
10 5 * * *  ~/anicast/scripts/prune-docker-cache.sh >> ~/anicast/backups/maintenance.log 2>&1
```

Offsite copies live longer than local ones: rclone deletes remote objects only
after 90 days (`--min-age 90d` in all three backup scripts), while local Sunday
dumps keep 60 days. Host timezone is UTC. Install idempotently with `python3 scripts/install-backup-schedule.py`; unrelated crontab entries are preserved. Target RPO: DB 6h, media 24h, conditional on successful offsite upload (alerts fire later — `db>7h`, `posters>26h`, `recovery-kit>8d` — so one missed run pages only after the slack window, not on the first hiccup). Target RTO: 2h after a suitable recovery host and credentials are available; it is not yet a guaranteed end-to-end SLA.

The newest successful DB dump is recorded in `backups/db/last_backup`. Separate `last_offsite_backup` markers are written only after upload succeeds. Missing rclone and failed uploads fail the job. `BACKUP_NOTIFY=0` suppresses messaging during manual tests. Freshness is exported through node-exporter; alerts cover stale copies and stopped metric updates. A failed backup sends a Telegram message through the ops bot and exits non-zero; a failed offsite upload still alerts even when the local dump succeeded.

`prune-docker-cache.sh` removes only BuildKit cache older than 24 hours. It does not prune images, containers or volumes, so production and image rollback remain available. The daily limit prevents rapid local-image builds from filling the MainServer root filesystem and triggering `DiskSpaceWarning`.

DB restore runbook:

```bash
# Safe: restore the newest dump into a scratch database, sanity-check it, drop it.
scripts/restore-db.sh --verify [dump]

# Destructive: replace the production database (stops backend and Celery first).
scripts/restore-db.sh --force [dump]
```

`--force` requires typing the production database name, takes a pre-restore backup first (aborts if it fails), holds a lockfile against a concurrent `backup-db.sh`, then drops and recreates the database, restores with `pg_restore`, brings the stack back and waits for backend health. Dumps contain user PII; the Google Drive copy is encrypted with keys stored in `~/.config/rclone/rclone.conf` and encrypted offline recovery kits; the decryption identity stays on the operator workstation.

### Migrating rclone to a project-owned Google Drive client

The project-owned Desktop client **Anicast rclone recovery** is active on MainServer
since 09.09.2026 (Moscow time), in project `anicast-backups-506301`. The owner
completed consent. Forced refresh succeeded on Windows and MainServer; encrypted
write/read/delete and independent retrieval of a fresh DB dump passed. Drive API
is enabled and the app has Production status; this avoids the seven-day Testing
token limit but does not mean public Google verification. The previous configuration
is retained privately as `rclone.conf.pre-oauth-20260908T234538Z` for rollback.
Both recovery kits were refreshed and downloaded/verified from Drive on Windows.
See [verification record](../archive/releases/RELEASE-2026-09-09-oauth.md). Procedure for future migrations:

1. Create (or pick) an owned Google Cloud project, enable the Drive API and create an OAuth client ID of type *Desktop app*. Note the client id and secret.
2. On MainServer back up the current config: `cp ~/.config/rclone/rclone.conf ~/.config/rclone/rclone.conf.bak-$(date -u +%Y%m%d)` (keep until the new client is proven).
3. The crypt remote `gdcrypt:` sits on top of a plain drive remote; the client credentials live on the **underlying** remote. Run `rclone config`, choose the underlying remote (not `gdcrypt`), set `client_id` and `client_secret`.
4. Re-authorize on the workstation with `rclone authorize drive --auth-no-open-browser`. Supply client ID/secret through private process environment, never shell history or chat. Store output privately; preserve the existing crypt keys and backup root folder. The owner handles Google security interstitials.
5. With the candidate private config, upload/read/check/delete a uniquely named probe in the backup folder, then atomically select that config. Run `BACKUP_NOTIFY=0 scripts/backup-db.sh`; verify token refresh and offsite retrieval. Regenerate both age kits and verify them from the workstation.
6. Keep the `.bak` config for ~30 days, then remove it.


## Isolated offsite recovery drill

Download the chosen DB dump and optional media archive from `gdcrypt:` into a
private directory (0700, files 0600), retaining their original backup timestamps
and SHA-256. Transfer only these inputs and drill scripts to the recovery host.
Preload the selected immutable backend and PostgreSQL images; no build is needed.
Ensure sufficient disk for archive, expanded media (up to 2 GiB), DB and images.

```bash
# On a separate recovery host, with Docker available. Arguments are paths and
# immutable image references, never credentials. Omit the last argument for DB only.
umask 077
python3 scripts/restore-isolated.py /private/backup.dump \
  ghcr.io/otakyooo/anicast-backend@sha256:<64-hex-digest> \
  postgres@sha256:<64-hex-digest> /private/posters.tar.gz
```

The utility refuses to start below 448 MiB MemAvailable (split inside: 128m media
extract, 192m PostgreSQL, 160m app, 0.4 CPU, `memory-swap == memory`). Do not lower this guard
to fit a busy VPS: wait for transient work to finish or use another host. It uses
new random volumes, an internal network, no public ports, no real runtime secrets,
no workers and a SELECT-only database role for the initial API probes. A separate process tests synthetic session login, one-use password reset, in-memory email, captured Telegram delivery and signed playback resolution inside a rolled-back transaction on the disposable DB. Media extraction is
streamed and bounded, followed by a read-only volume mount. Keep the shell alive
until completion; after an interrupted process, inspect and remove only its exact
`anicast-restore-<id>-*` resources. Never use global Docker prune as cleanup.

Record aggregate counts, backup dates/hashes, API result and restore duration.
Confirm no temporary containers/volumes/networks remain, check public health and
memory, then remove only the explicitly named transferred drill inputs. Do not
delete scheduled local/offsite backups. Duration excludes fetching images/data
and is not an end-to-end RTO. Set `DRILL_CUTOVER=1` and preload the pinned Caddy image to rehearse private proxy switch/rollback against a real restored HTTP API. External video streaming, delivery to real mailboxes/chats and a public traffic cutover remain separate operations. This drill does not restore production.

`restore-db.sh --verify` remains a lighter local DB check, with a unique scratch
name. It refuses an existing scratch DB instead of dropping it; it cannot replace
an independent-host recovery drill.


## Восстановление без MainServer и перенос API/БД

### Что уже можно восстановить

Зашифрованные age-комплекты обоих серверов копируются на компьютер оператора.
MainServer дополнительно загружает их в `gdcrypt:recovery` раз в неделю.
Комплект содержит runtime env, release manifest, Compose и release scripts,
rclone config с ключами crypt, SSH к VPS, registry и monitoring. VPS-комплект
добавляет Caddy, firewall и AWG. Ключ расшифровки — личный `anicast_deploy`,
он не переносится на серверы. Не хранить единственную копию комплекта только
в gdcrypt: для получения crypt keys сначала нужен сам комплект.

На компьютере оператора проверка не создаёт открытых файлов:

```sh
python scripts/verify-recovery-kit.py /private/mainserver.age \
  --identity /private/anicast_deploy --age-bin /tools/age
```

Windows: фактические копии находятся в `C:\Users\Nasa\.ssh\anicast-recovery`;
доступ ограничен текущим пользователем и SYSTEM. Бинарники age/rclone находятся
в `recovery-tools/windows` рабочего каталога. Идентификатор клиента Google не
является ключом расшифровки. Нужны именно SSH identity и age-файл.

Для восстановления экспортировать из расшифрованного архива только нужные
файлы в приватный каталог. Никогда не выводить их содержимое в терминал/чат и
не распаковывать поверх production. Восстановленный rclone config позволяет
скачать выбранные DB/media; проверить SHA-256 sidecar до использования.
SSH key и known_hosts из комплекта дают прямой доступ к публичному VPS с
HostKeyAlias=10.78.0.1. Проверка этого пути с Windows уже выполнена.

После смены OAuth, registry credentials или runtime env пересоздать оба
комплекта, скопировать на компьютер и проверить. Ещё одна копия личного ключа
на отдельном носителе защищает от одновременной потери компьютера и серверов;
создание такой физической копии в этой работе не проверялось.

### Репетиция

Передать на recovery-host только dump/media и `restore-isolated.py`,
`recovery-smoke.py`, `recovery-flows.py`, `recovery-media.py`, `recovery-http.py`.
Предварительно загрузить backend/PostgreSQL из release manifest и Caddy digest
из текущего Compose. `DRILL_CUTOVER=1` включает отдельный Caddy без host ports.

Проверки: миграции/связи/агрегатные количества, чтение каталога и media,
синтетический session login, reset пароля с запретом повторного токена,
email в памяти, Telegram capture sink, signed playback issue/resolve,
переключение отдельного reverse proxy на восстановленный HTTP API и обратно.
Пользовательские записи не изменяются в production; тестовые записи откатываются.
Реальная отправка людям и загрузка видео стороннего провайдера не имитируются
успехом. После теста уникальные containers/volumes/network удаляются.

### Постоянный перенос

Нужен предоставленный внешний сервер. Начальный ориентир для полного data tier:
2 vCPU / 4 GiB RAM, SSD с запасом не менее двух объёмов DB/media и места под образы.
Это стартовый бюджет, не гарантия ёмкости под произвольную нагрузку. Текущий VPS
с 1 GiB остаётся edge/frontend. После увеличения RAM домашнего MainServer
09.09.2026 ОС видит 3606 MiB; CPU остаётся один. Это улучшило запас ресурсов, но не
устранит зависимость от дома.

1. Сохранить публичный VPS и DNS: перенос API не требует смены доменного адреса.
   На новом хосте настроить Docker, firewall, VPN к VPS с новым ключом и закрытый
   адрес API. Копии private key старого MainServer AWG в комплекте нет; новый peer
   создаётся через восстановленный root-доступ к VPS. Проверить MTU и media.
2. Восстановить пробную копию, пройти репетицию и настроить backup/monitoring на
   новом хосте. Не запускать beat/уведомления против пробных пользовательских данных.
3. Для финального переноса включить короткое обслуживание, остановить beat и
   API-писателей, корректно завершить workers. Снять окончательные DB/media и
   persistent Redis AOF после остановки. При наличии pending jobs сохранять broker
   и coordination вместе; не очищать очередь и не запускать два beat одновременно.
4. Восстановить окончательные данные на новом узле под прежними именами Compose
   project/volumes. Проверить миграции, пользователей, media, readiness и workers.
5. Создать новые immutable runtime env на VPS: API_UPSTREAM для Caddy и
   API_INTERNAL_URL для frontend должны указывать на один новый backend. Сохранить
   прежние manifest/Compose. Применить, затем проверить login, catalog, player,
   private endpoints, relay и независимый мониторинг через публичный домен.
6. До допуска записей возможен возврат прежнего upstream. После появления новых
   записей на новом сервере простой возврат на старую DB потеряет данные: сначала
   остановить писателей и согласовать актуальную DB/media/queues. Старый MainServer
   некоторое время сохраняется выключенным как источник отката, без активного beat.

Цели RPO: DB 6h, media 24h при успешном offsite; цель RTO 2h после доступности
recovery-host/credentials. Время конкретного теста и ограничения — в отчёте релиза.
Постоянный перенос не выполнен, пока пользователь не предоставил внешний хост.

### Zero-budget standby (без покупок)

Платный переезд не планируется. Вместо HA — быстрый ручной failover:

1. Держать оба age-комплекта свежими после каждой смены OAuth/registry/env и
   проверять `verify-recovery-kit.py` с операторского компьютера; вторая копия
   личного ключа — на отдельном носителе.
2. Второй бесплатный офсайт: отдельная папка Drive + локальная копия дампа на
   компьютере оператора после каждого Sunday-kit; `SHA-256` sidecar сверять до
   использования.
3. Холодный standby — любой доступный бесплатный хост с Docker
   (домашний ПК, free-tier): `restore-isolated.py` + `DRILL_CUTOVER=1` с
   образами из release manifest, затем смена `API_UPSTREAM`/`API_INTERNAL_URL`
   на VPS. Старый MainServer держать выключенным как источник отката, без beat.
4. Окна обслуживания — `03:00–05:00 UTC`, короткие, только `expand/contract`,
   без `kill -9` bulk (grace 1900s). Замерять сквозной drill с секундомером
   (fetch+restore+edge) и записывать факт, не цель.
