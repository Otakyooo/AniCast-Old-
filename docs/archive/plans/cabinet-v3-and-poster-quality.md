# Кабинет v3 + пиксельные постеры

Две задачи из плана. Vue — забыть (решение зафиксировано).

## Задача 1: Пиксельные постеры — новый тир `o` (Shikimori original)

**Диагноз.** Пайплайн уже хранит `poster_origin_url` (Shikimori original, обычно
1000–3000px), но никогда не использует его как апгрейд: origin расходуется только
как mirror-фолбэк в тире `s` при потере файла. Тайтлы, застрявшие в `s`/`l`/`k`
(маленькие файлы 225–460px), рендерятся в hero на 280+ CSS px (×2 на retina) —
отсюда пиксельность. Jikan наполовину лежит, поэтому путь через `m` часто недоступен.

### `backend/catalog/posters.py`

1. `TIER_ORIGIN = "o"` после `TIER_KITSU`.
2. `POSTER_NAME_RE`: `[mlsk]` → `[mlsko]`.
3. Docstring: добавить строку про `o` (уже подготовлена).
4. `_adopt()` verb map: `"o": "original"` (для полноты, хотя o идёт через `_adopt_if_larger`).
5. `_adopt_if_larger`: метрика/результат обобщить:
   ```python
   verb = {"k": "kitsu", "l": "large", "o": "original"}[tier]
   increment("poster_refresh", verb)
   return verb, f"{title.slug}: stored {filename} ({width}x{height}, {ext})"
   ```
   (сейчас там тернарник kitsu/large).
6. `refresh_title()` — вставить origin-пробу после ветки Jikan-maximum, перед
   логикой large/kitsu:
   ```python
   origin = title.poster_origin_url
   if origin and is_allowed_poster_url(origin):
       upgraded, detail = _adopt_if_larger(title, mal_id, origin, TIER_ORIGIN, apply_changes)
       if upgraded == "original":
           return upgraded, detail
   ```
   Падения (error/invalid/current) проваливаются в существующую логику l/kitsu —
   отказ origin не ломает остальные источники.
7. `_candidate_priority()`: `if tier == TIER_ORIGIN: return 2` (рядом с l/k).

### `backend/catalog/test_posters.py`

- Обновить `test_adopt_records_remote_origin` (вторая часть): после удаления
  локального файла refresh теперь восстанавливает из origin как тир `o`
  (результат `"original"`, `"-o-"` в URL) вместо mirror `s` — строго лучше,
  origin сохраняется.
- Новые тесты:
  - `test_origin_upgrade_replaces_smaller_fallback` — s-тир 225×318, origin
    shikimori, download 800×1200, Jikan None → `"original"`, `"-o-"` в URL,
    старый файл удалён, origin не изменился.
  - `test_origin_smaller_keeps_stored_and_falls_through` — l-тир 500×700,
    origin отдаёт 300×446, Jikan large 425×600 → `"current"`, скачивания
    `[origin, mal_large]`, файл на месте.
  - `test_origin_tier_priority_bucket` — `_candidate_priority(...) == 2`.
  - regex: `POSTER_NAME_RE.match("21-o-ab12cd34.jpg")` истинно.

### Прогон

Штатный `refresh_title_posters` (beat, каждые 6ч, 120 тайтлов/прогон) сойдётся
к лучшему качеству без ручных действий; для немедленного прогона —
`manage.py backfill_posters --apply` на проде в тихий час.

## Задача 2: Кабинет v3 — превью коллекций + персональные рекомендации

Бэкенд не трогаем: `GET /api/v1/collections/` уже возвращает коллекции с items
(вложенные тайтлы с poster_url), `GET /api/v1/recommendations/?page=1` уже
персональный. Оба блока — клиентские композиции по паттерну `RecentNotes`
(коллапс для гостей/пустых/ошибок, AbortController).

### Новые файлы

1. `frontend/components/collection-previews.tsx`:
   - `getCollections()` → до 3 коллекций;
   - карточка: имя, счётчик (`collections.itemCount`), до 4 постеров
     (`next/image`, `fill`, `sizes="72px"`, `referrerPolicy="no-referrer"`),
     ссылка на `/collections/manage/{slug}`;
   - заголовок «Мои коллекции» + ссылка «Смотреть все →» на
     `/library?view=collections`;
   - `null` при пустоте/ошибке.
2. `frontend/components/recommendation-shelf.tsx`:
   - `getRecommendations(1)` → топ-6, сетка `catalog-grid` из `CatalogCard`;
   - заголовок «Вам может понравиться» + ссылка на `/recommendations`;
   - `null` для гостя (401 → `getRecommendations` вернёт null) и пустоты.

### Изменённые файлы

3. `frontend/components/account-panel.tsx` — вставить блоки в порядке:
   stats strip → ResumeShelf → CollectionPreviews → жанры →
   RecommendationShelf → RecentNotes → quick links.
4. `frontend/app/profile.module.css` — классы `.collectionCard`,
   `.posterRow`, `.posterThumb` (72×104, object-fit cover, радиус как у
   соседних карточек) в существующей стилистике токенов.
5. `frontend/i18n/dictionaries.ts` — ключи RU/EN:
   - `account.collectionsHeading`: «Мои коллекции» / "My collections";
   - `account.recommendedHeading`: «Вам может понравиться» / "You may also like";
   - переиспользуем: `home.showAll`, `collections.itemCount`.

### Тесты

- `frontend/lib/account-summary.test.ts` не расширяется (чистая композиция);
  проверка — typecheck + lint + build + живой smoke против заглушки API
  (как в SEO-итерации): аккаунт с сессией рендерит оба блока, гость — ни одного.

## Валидация (весь набор)

- backend: `pytest` (все), `ruff check .`, `mypy .`, `makemigrations --check`;
- frontend: `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`;
- `sh scripts/validate.sh`, `git diff --check` (без CRLF);
- обновить `docs/IMPLEMENTATION_STATUS.md` (секция «Кабинет v3», снять пункт
  с «Следующих задач», отметить тир `o` в постер-пайплайне).
