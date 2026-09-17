# Релиз 17.09.2026: зависимости, python 3.14 / node 26, ремонт GitHub (`981e9d05`)

Код `981e9d05`, манифесты коммита `3f569e12`, запушены в `origin/main`. Образы —
GHCR по immutable digest (путь `publish`, не локальные):

- backend `ghcr.io/otakyooo/anicast-backend@sha256:7e19c83cbdd2170e1133a6e1b0d46ef88d13f10b7cd473588160408a3a7bb6f4`
- frontend `ghcr.io/otakyooo/anicast-frontend@sha256:09230f115c0c5a5e312b6505cdb99b2a065f7cec9577124cf9cdac7438c8462a`

Откатная база: MainServer `/var/lib/anicast/releases/mainserver`
(current=981e9d05, previous — релиз на f12dd800, ещё три поколения); VPS
`/var/lib/anicast/releases/vps`. Recovery kits пересобраны в `gdcrypt:recovery`
(`mainserver-20260917T023534Z.age` — 22 файла, `vps-20260917T023534Z.age` — 12);
расшифровка проверяется оператором на рабочей станции (identity на серверах не хранится).

## Что изменилось

- Ремонт GitHub: на main отправлен зависший `fix(infra)` (checkpoint_timeout=30min
  — фикс уже жил на MainServer, а репо отставал) и `release/release.json`.
  Зависшая backup-ветка `backup/pre-integration-20260916-232212` оставлена как
  архив (единственный расхожий кусок — дофиксенный `theme.css` с контрастом ниже
  WCAG AA; на main исправлено).
- Зависимости (изоляционная проверка перед мерджем): djangorestframework 3.17.2→3.18.1;
  psycopg 3.2.10→3.3.5 **вместе с companion-пином** `psycopg-binary` в constraints.txt
  (dependabot не знает про constraints-файл, его PR #5 резолвился в `ResolutionImpossible`);
  uvicorn 0.35.0→0.52.4; @types/node 24.3.0→26.5.0 (точный пин, не `^`).
- Рантаймы: python 3.12-slim→3.14-slim и node 22-alpine→26-alpine (базовые образы
  по digest). `API_INTERNAL_URL`/`NEXT_PUBLIC_SITE_URL` вшиваются в образ при сборке
  (publish.yml), поэтому образ фронтенда корректен для VPS и без runtime-override.
- Не принято: typescript 5.9→7.0 (typescript-eslint внутри eslint-config-next не
  поддерживает TS 7) и eslint 9.34→10.10 (eslint-plugin-react зовёт удалённый
  rule-context API). Findings оставлены в комментариях PR #10/#11.

## Аудит (до релиза)

- MainServer: все 8 сервисов healthy, readiness OK, оба Celery worker проверены
  раздельно (pong), beat активен по логам; `verify-monitoring.sh` — 3 Redis-роли up,
  backend скрейпится; `/internal/metrics` снаружи 404; capacity 24h: scrape_up 100%,
  RAM available min 662 / p95 1789 MiB, CPU busy p95 30% (max 86.5% в окне импорта),
  iowait p95 2.5%; активен warning `SwapActivityHigh` (swap-спайки до ~4.3k pages/s
  в окне импорта/чекпоинтов) — OOM/перезапусков нет, памяти достаточно, но в пики
  под давлением.
- VPS: frontend/caddy healthy, loopback + публичные edge-пробы, relay слушает
  `10.78.0.1:8443` (не `*:8443`), `getMe`→401 и `/`→404 (не открытый прокси),
  hairpin-запрос из frontend-контейнера к публичному origin — 200.
- Бэкапы: cron каждые 6 ч (последний `anicast-20260917T001501Z.dump`), свежий ручной
  прогон `BACKUP_NOTIFY=0` — exit 0; poster-том от 09-16 (369 MB / 7656 файлов);
  offsite-копия загружается. RPO 6 h DB / 24 h media.
- Код: pytest 386 passed, ruff/mypy/`makemigrations --check`/`check --deploy` чистые,
  pip-audit без уязвимостей; frontend — typecheck, eslint, 87 unit, production build,
  npm audit 0 уязвимостей; `validate.sh` (hermetic deploy/rollback) прошёл.
- Браузеры: `e2e-browsers` workflow (Chromium + Firefox + WebKit) — success.

## Выкладка

- MainServer первым: образ стянут, `check --deploy`, `migrate`, staged rollout
  (API → default worker + beat → bulk с warm shutdown), `deployment verified for
  mainserver`, автоотката не было. В контейнере — Python 3.14.7, digest совпал с
  манифестом.
- VPS вторым: `/opt/anicast` синхронизирован (scripts + `infra/vps/compose.yml` —
  копия отстала от main на staged-rollout скрипты), манифест перенесён в `/tmp`,
  `deployment verified for vps`. В контейнере — node v26.8.2, digest совпал.
- После релиза: `/` 200 за ~0.88 с, `/api/v1/titles/?page_size=1` 200 за ~0.54 с,
  `/internal/metrics` 404; оба стека `verify-deploy` зелёные.

## Остаток

- Коллекции реализованы, но без browser E2E (создание/добавление/порядок/публичная
  ссылка) — приоритет №1 следующих проверок; контракт зафиксирован в ADR 009.
- `SwapActivityHigh` — наблюдаемое предупреждение, не инцидент; RAM-даунгрейд не
  требуется, но лимиты импорта держать.
- TS 7 / eslint 10 — ждать совместимости eslint-config-next и его плагинов.
- Токен оператора (которым был поделился) скомпрометирован (публичная вставка +
  plaintext в `~/.git-credentials`): ротация отложена по решению оператора, должна
  быть выполнена вручную.
