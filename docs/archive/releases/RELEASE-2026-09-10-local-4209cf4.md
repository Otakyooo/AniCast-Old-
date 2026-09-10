# Локальный релиз 4209cf4: фиксы описаний и счётчиков — 10.09.2026

## Контекст

Запрос владельца: выложить текущую версию (`4209cf4`) на продакшен. После
релиза [092c630](RELEASE-2026-09-09-ux-redesign.md) владелец запушил
`8b30ee3 fix(ux): show descriptions and end conflicting counters`, удалил
PNG из docs и затем удалил `.github/workflows/ci.yml`, `publish.yml` и
`dependabot.yml` (коммиты `c80751d`, `3e0b386`, `4209cf4`).

Проверка GHCR: образов `sha-8b30ee3…` нет (`manifest unknown`), тег `main`
указывает на образы 092c630 — publish для `8b30ee3` не завершился. CI-путь
закрыт удалением workflows, поэтому выпуск выполнен по документированному
пути локальных образов (`ANICAST_LOCAL_IMAGES=1`, DEPLOYMENT.md «Release
state and bootstrap»). Код приложения в `4209cf4` идентичен `8b30ee3`
(остальные коммиты удаляют только workflows/dependabot/PNG).

## Проверки перед выпуском (чек-аут MainServer, HEAD 4209cf4, дерево чистое)

- Backend: `ruff check`, `mypy` (152 файла), `pytest` — 342 прошли
  (staticfiles-манифест свежий в /tmp, исходники статики не менялись),
  `makemigrations --check` не требуется (моделей не касались), деплой-скрипт
  сам прогнал `check --deploy` в prod-env.
- Frontend: `eslint`, `tsc --noEmit`, 77 unit, production build,
  E2E Chromium 60 сценариев на 1440/1280/820/390.
- Известный флейк: `session-player: player restores position…` (ожидание
  «Не удалось сохранить прогресс» после смоделированного 503) упал 2 раза из
  4 прогонов полного suite и прошёл 4/5 изолированных запусков. Изменение
  `8b30ee3` в watch-space касается только подписей счётчиков и не трогает
  поток сохранения; флейк наблюдался и на 092c630 (мобильный viewport,
  прошёл при повторе). Тайминговая нестабильность, не регрессия.

## Сборка и выпущенные образы

Сборка на MainServer (`docker build`, кэш слоя ускорил frontend; RAM
пережила через swap):

- backend `sha256:b050bb459df9516900e10d72429cf6c0a165daf837195b53e29716b95d4f0523`
- frontend `sha256:78dbff2efdf859afd722984487d64451fa4580d1e260e9883bd8c53851dced09`
  (build-args публичных Telegram-имён как в прежнем publish.yml)

RELEASE_SHA: `4209cf4d98ae17512668c75fe41b7d9e6ebbbebb`.

Pre-deploy: `BACKUP_NOTIFY=0 scripts/backup-db.sh` — проверенный дамп
`anicast-20260910T161656Z.dump` (3624640 bytes), `last_backup` обновлён.

## Выкладка

MainServer (state dir `~/anicast/backups/releases/mainserver`, runtime env
`predeploy-20260909-hardening/runtime.env`): data-сервисы → backend
(`check --deploy` в compose-env) → worker/beat → bulk; все health gates
прошли, `deployment verified for mainserver`. Отдельно проверены оба
работника: `celery inspect ping` в `celery-worker` и `celery-bulk` — pong.

VPS (`/opt/anicast`, runtime env `anicast-security-13286f9/runtime.env`):
образ передан `docker save | gzip | ssh docker load` (34G свободно),
`deployment verified for vps`.

Публичные проверки: `/` 200, `/api/v1/titles/?page_size=1` 200,
`/internal/metrics` не 200 снаружи. Image ID запущенных контейнеров совпадают
с манифестами. Новое поведение на проде: составная строка покрытия
«Доступно 1120 из 1180» на странице Ван-Писа; `/episodes/recent/?days=30`
(30-дневное окно полки) — 2 серии; RU-синопсисы возвращаются
(per-field fallback `8b30ee3`).

## Откат и ограничения

- Откат: `scripts/rollback.sh mainserver|vps` — previous-манифесты указывают
  на registry-дайджесты 092c630, образы всё ещё в GHCR, откат рабочий без
  локальных образов.
- Локальные образы `release-20260910` необходимо сохранить до выхода
  следующего релиза: повторный деплой/откат вперёд текущей версии требует их
  наличия (или пересборки).
- CI/publish workflows были удалены владельцем после релиза: во время выпуска
  этого релиза GHCR-сборка и гейты не работали. Workflows восстановлены из
  `b52e642` следующим коммитом; `pip-audit` в этом выпуске не выполнялся.
- Релиз-запись и восстановление workflows отправлены в GitHub владельцем
  после повторной настройки учётных данных.
