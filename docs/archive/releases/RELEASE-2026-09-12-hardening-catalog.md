# Релиз 12.09.2026: hardening-аудит и фикс каталога (MainServer)

Коммиты: `a74590c` (P0–P3 zero-budget hardening), `9388b66` + `a8d7a13`
(фикс запросов каталога). Образы локальные (`ANICAST_LOCAL_IMAGES=1`,
motivation — та же, что в `RELEASE-2026-09-10-local-4209cf4.md`):
backend `sha256:4706b1…` (`RELEASE_SHA=a8d7a13`). Frontend/VPS-фаза ждёт
GHCR-публикации (на хосте нет Node для сборки): запланирована отдельно.
Откатная база: `/home/lama_admin/.anicast-releases/mainserver`
(`current/previous/previous-2/previous-3`), предрелизный бэкап
`backups/db/anicast-20260912T011457Z.dump` (backup ok, 3.7 MiB).

## Ход

- Деплой №1 нового образа: гейт не прошёл, сработал штатный автооткат
  (`rollback verified`), прод остался на `release-20260910`. Точная фаза
  в обрезанном логе не сохранилась; повторный деплой того же образа —
  `deployment verified`.
- После деплоя `/api/v1/titles/` висел 25–120с (таймауты edge и прямых проб),
  при этом `/` открывалась. Диагностика (изолированные контейнеры старого и
  нового образов на той же БД): старый — 0.1–0.3с, новый — 10–50с.
  Харднинг-батч невиновен (его дифф этих строк не касается, `git diff
  8f98dca..a74590c` пуст по фильтру франшизы).
- Корень: изменения каталога из `934cda7` (11.09, прод их никогда не запускал —
  образ был от 10.09): коррелированный подзапрос точки входа франшизы на
  строку + rights-JOIN в playable-аннотации. EXPLAIN: 1.7M index probes,
  40k heap re-reads, `Execution Time: 4830ms` на 100 тайтлах / 29k источниках;
  под herd краулеров четыре gunicorn-потока вставали в очередь (каскад).
- Фикс с сохранением поведения (тесты `grouped`/`grants` зелёные): entry-id
  франшиз — один ordered scan в Python; playable — один GROUP BY по странице
  (`playable_episode_counts`), grants-ветка опускается пока таблица пуста;
  airing — то же для полки ≤12. Мёртвая коррелированная аннотация удалена.
- Деплой №2 (фикс): `deployment verified`, без откатов.

## Проверки после релиза (edge, серийно)

- `/` 200 за 0.79с; `/api/v1/titles/?page_size=1` 200 за 0.47с, `count: 78`
  (группировка сезонов), `playable_episodes_count` на месте;
  `seasons=separate` 0.48с; `/api/v1/titles/airing/` 0.42с (было 4.5–8с).
- `/internal/metrics` снаружи не 200. Все 8 сервисов `healthy` на новом образе.
- Backend: `pytest` 346 passed + 6 предсуществующих staticfiles-падений
  (как в статусе 11.09); `ruff`, `mypy`, `makemigrations --check`,
  `check --deploy` — чисто. Frontend: `lint/typecheck/build` — чисто и в CI,
  и локально (Node во временном каталоге); E2E: три падения `tab-pages`
  в CI оказались рассинхроном спек с UX 11.09 (свитчер в меню предпочтений,
  подпись «Статус выпуска», 4 ссылки вместо 6) — спеки поправлены
  (`8199ce8`), локально 72/72 на четырёх Chromium-вьюпортах.

## Остаток

- VPS (конфиг): `Caddyfile` (strip токена на `/staff|/static`), `compose.yml`
  (лимиты Caddy, healthcheck с Host-пробой), `firewall.nft`-копия и скрипты
  синхронизированы в `/opt/anicast`; деплой `deploy.sh vps` на текущем
  frontend-образе — `deployment verified`, Caddy `healthy`, edge titles 200.
  По дороге гейт поймал мою же ошибку (проба без Host всегда 404):
  исправлено `a1ff5d6`, gatehampton подтверждён повторным деплоем. Вывод:
  откат использует checked-out Compose, поэтому битый healthcheck роняет и
  откат до ручной правки — проверять гейты на синк-стенде до деплоя.
- VPS (фронт): новый образ только из GHCR-публикации (`a8d7a13+`, на хосте нет
  Node): после зелёного publish — `deploy.sh vps` с digest + edge-пробы.
- Наблюдать: PG CPU/load после прогрева, `EndpointGroupErrorRatio`,
  `SiteSlowWarning`; повторный затор каталога — сигнал к денормализации
  счётчиков, а не к очередному рефактору запроса.
- Ротация `INTERNAL_API_TOKEN`/`METRICS_BEARER_TOKEN` не выполнялась
  (секреты в git не попадали — проверено `validate.sh`-гейтом и сканом diff).

## Ротация токенов 12.09 ~11:10 UTC (выполнено)

Сгенерированы новые 64-символьные значения, разложены без печати:
MainServer `infra/mainserver/.env` (+`.bak` рядом) и
`infra/monitoring/secrets/metrics-token`; VPS `runtime.env` и
`/opt/anicast/infra/vps/.env` (+`.bak`). Совпадение проверено по SHA-256
префиксам, значения нигде не печатались. Backend и frontend пересозданы,
оба `healthy`; скрап Prometheus зелёный (`verify-monitoring.sh`),
edge 200. Старые `.bak` и `backups/predeploy-*` содержат уже мёртвые
значения — не удалять (история откатов), в проде они не используются.

ВАЖНО: оба age-комплекта теперь STALE (внутри старые env) — оператору
пересоздать kits и проверить `verify-recovery-kit.py` с рабочей станции
до следующего релиза. UPDATE 12.09 ~11:15 UTC: kits пересозданы на MainServer
(`backup-recovery-kit.sh`, оба комплекта + выгрузка в `gdcrypt:recovery` OK).
Оператору осталось скачать новые комплекты на компьютер и проверить
расшифровку — без этого восстановления пойдёт по старым токенам. Наблюдение: прямые пробы хоста на `10.78.0.2:8000`
стали упираться в таймаут после пересоздания (docker-proxy слушает,
туннель и sidecar-пути зелёные) — на прод не влияет, отдельный пункт
для разбора, не следствие ротации как таковой.
