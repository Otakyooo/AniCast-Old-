# Страница тайтла: герой, обзор, запросы + релиз в прод

Тема выбрана пользователем делегирована. Приоритет роли §18: страница аниме —
информационный центр произведения. Все правки фронтендовые; миграций нет;
URL и вкладки не меняются.

## Фаза 0 — отправить в прод незакоммиченную работу (home/discovery)

Рабочее дерево содержит завершённую и проверенную итерацию
(рейтинги на карточках, рельсы полок, combobox-поиск, тулбар каталога,
compact franchise payload). Задача — довести её до production:

1. Коммит одной пачкой в стиле репозитория, например:
   `feat: community ratings on cards, shelf rails and keyboard search`
   (включая `docs/IMPLEMENTATION_STATUS.md`, план, `backend/conftest.py`,
   удаление двух conftest-дубликатов). Push в `origin/main`.
2. Преддеплойный бэкап: `scripts/backup-db.sh` (verified dump) на MainServer;
   записать текущие дайджесты образов для отката.
3. Релиз по рунбуку OPERATIONS.md «Local-image releases» (GHCR-токен только
   read:packages, действующий путь — локальная сборка):
   - `stamp=$(date -u +%Y%m%dT%H%M%SZ)`;
   - backend: `docker build -t anicast-backend:local-$stamp backend`;
     `sed -i BACKEND_IMAGE` в `infra/mainserver/.env`;
     `migrate --plan` (ожидаемо пусто — миграций нет);
     `docker compose -f infra/mainserver/compose.yml up -d backend celery-worker celery-beat`;
   - frontend: сборка с ОБАМИ переменными
     `--build-arg NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=anicast_auth_bot`
     `--build-arg NEXT_PUBLIC_TELEGRAM_NOTIFY_BOT_USERNAME=anicast_push_bot`
     (пропуск молча отключает Telegram-флоу);
     `docker save | gzip` → `scp root@10.78.0.1:/tmp/` → `docker load` →
     `sed FRONTEND_IMAGE` в `/opt/anicast/infra/vps/.env` →
     `docker compose up -d frontend` на VPS;
   - публичный smoke: `/` 200, `/api/v1/titles/?page_size=1` 200,
     `/internal/metrics` НЕ 200; удалить tarball с обоих хостов.

## Фаза 1 — итерация «Страница тайтла»

### A. Рейтинг в герое

- В `heroMeta` добавить чип `★ 7.5 · N` при `rating_count >= порога`
  (детальный payload уже аннотирован в прошлой итерации); чип — ссылка на
  `?tab=community`. Tooltip числовой `7.5 / 10 · N` (без плюрализма).
- Порог вынести из `catalog-card.tsx` в общий модуль `frontend/lib/rating.ts`
  (`MIN_RATING_VOTES = 3` + helper `cardRating(item)`), чтобы константа не
  разъехалась между карточкой и героем.

### B. Блок «Детали» без дублей

Заменить четыре повтора (формат/статус/эпизоды/жанры — они уже чипы героя) на:

- Формат (как был);
- Длительность серии: `duration_minutes` (сейчас в payload, нигде не показан),
  формат «~24 мин» / "~24 min", скрывать ячейку при null;
- Франшиза: имя со ссылкой на `/franchises/<slug>` (страница существует,
  редиректит только индекс), скрыть при отсутствии;
- Оригинальное название (`original_name`), скрыть при отсутствии.

Ключи i18n RU/EN: `title.duration`, `title.franchiseLabel`;
переиспользовать существующие для формата.

### C. Общий класс полки вместо двух больших сеток

- Перенести responsive-поведение `.shelfGrid` из `home.module.css` в глобальный
  `.catalog-shelf` в `globals.css` (desktop: сетка 6/5/4 колонок как у
  `.catalog-grid`; <1024px: snap-рельс) — системное решение вместо копии.
- `home/page.tsx`: `styles.shelfGrid` → `catalog-shelf`, правила удалить из модуля.
- На overview-вкладке тайтла `related_titles` и `similar` перевести с
  `.catalog-grid` на `.catalog-shelf` — обзор перестаёт быть простынёй на
  мобильных, поведение совпадает с главной.

### D. Локализованные даты эпизодов

- `EpisodeCard` рендерит `air_date` через `Intl.DateTimeFormat` с локалью
  активного языка (`intlLocale` из `i18n/config`; серверный рендер —
  детерминированный, hydration не затронут). Проверить, что `getI18n()`
  отдаёт locale; если нет — взять из cookies тем же способом, что и server.ts.

### E. Убрать N+1 в подборе коллекций

- `TitleCollectionControl`: `GET /api/v1/collections/` уже возвращает вложенные
  `items[].title.slug`; убрать `Promise.all(result.map(getCollection))` и
  вычислять `included` прямо из списка → один запрос вместо 1+N
  (до 51 запроса на просмотр страницы при большой библиотеке).
- Тип `CollectionSummary` должен содержать `items`; при необходимости расширить
  тип в `lib/collections.ts`.

## Не входит в scope

- Embed playback, pg_trgm-ранжирование поиска, визуальный QA в браузере
  (surface недоступен — отметить в итоге), редизайн вложенного payload
  collections API.

## Валидация

После каждой фазы:

- Backend: `pytest` (200 passed), `ruff check .`, `mypy .`,
  `makemigrations --check --dry-run` (миграций нет).
- Frontend: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`.
- `sh scripts/validate.sh`, `git diff --check`.
- Деплой по фазе 0 шагами 2–5, публичный smoke после каждого стека.
- `docs/IMPLEMENTATION_STATUS.md` — секция итерации с фактом деплоя
  (штампы образов, дамп, точки отката).

## Риски

- Прод-деплой: откат только образов (без БД) — обе итерации без миграций,
  совместимы в обе стороны; предыдущие дайджесты фиксируются перед релизом.
- SSH `root@10.78.0.1` и docker на MainServer используются рунбуком —
  предполагаются доступными; при недоступности VPS задеплоить backend и
  зафиксировать остаток как открытый пункт.
- Сборка frontend без NEXT_PUBLIC_* аргументов ломает Telegram-кнопки —
  аргументы прописаны в плане и проверяются smoke'ом страницы входа.
