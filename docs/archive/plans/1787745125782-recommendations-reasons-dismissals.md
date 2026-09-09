# Рекомендации: причины, честный скоринг и «Не интересно»

## Контекст

`/recommendations` и полка на `/account` построены на `RecommendationListView`
(backend/library/views.py:309). Текущие проблемы:

1. UI показывает сырой чип «Релевантность: 4.5» (`recommendations.score`) — число без смысла; API не отдаёт причин.
2. Нет негативных сигналов: дропнутые жанры и низкие оценки (≤4) не штрафуют.
3. Бонус франшизы плоский (+3.0) — не зависит от вовлечённости.
4. Тайтлы, полностью просмотренные через историю (без записи в библиотеке), всё ещё рекомендуются.
5. Tie-break равных скоров по году/имени без учёта рейтинга сообщества.

Решение пользователя: включить кнопку «Не интересно» (dismiss) в эту итерацию.
Стек, URL страниц, авторизация — не меняются. Миграция одна (expand-only).

## Изменения

### Backend

**1. Модель `RecommendationDismissal` (backend/library/models.py + миграция)**

- Поля: `user` FK (related_name="recommendation_dismissals", CASCADE), `title` FK
  (related_name="recommendation_dismissals", CASCADE), `created_at`.
- Constraints: `UniqueConstraint(user, title)`; Index(fields=["user"]).
- Админка: read-only в `/staff/` (пользовательские данные), как library-модели.

**2. API dismissals (backend/library/urls.py, views.py)**

- `POST /api/v1/recommendations/<slug>/dismiss/` → 201; повторный вызов → 200
  (idempotent get_or_create). `DELETE .../dismiss/` → 204; чужой/несуществующий
  slug → 404. Оба: `IsAuthenticated`, CSRF через SessionAuthentication
  (паттерн `LibraryEntryView`).
- `RecommendationListView.get_queryset()`: дополнительно исключить
  `id__in=RecommendationDismissal.objects.filter(user=user).values("title_id")`.

**3. Скоринг в `RecommendationListView`**

- Негативные веса: жанры DROPPED-записей → −1.0 за жанр; жанры тайтлов с оценкой
  ≤4 → −0.5. Позитивные фильтры кандидатов строятся только из положительных весов
  (`genres__id__in=positive_keys`); в сумму скора входят все веса (позитив+негатив).
- Cold-start условие: fallback «по новизне» срабатывает когда нет положительных
  весов (сейчас — когда пуст dict). Только дропы → fallback, а не пустая выдача.
- Франшизный бонус масштабируется от вовлечённости:
  `min(count_non_dropped_library_entries_in_franchise, 4) * 1.5` вместо flat 3.0.
- Исключение полностью просмотренных: два bounded-агрегатных запроса
  (число эпизодов по тайтлам из EpisodeProgress пользователя vs число
  просмотренных); title с `episode_count > 0 and watched == episode_count`
  исключается из выдачи (продолжение просмотра покрывает ContinueWatching).
- Tie-break качества: аннотировать `rating_avg`/`rating_count` существующим
  `annotate_rating_aggregates`; порядок `-score`, `F("rating_avg").desc(nulls_last=True)`,
  год desc, name, slug.

**4. Причины в ответе (additive, обратно совместимо)**

- Элемент ответа: `{title, score, reasons}` где
  `reasons = {genres: ["Драма", "Комедия"], franchise: bool}`.
- View передаёт в serializer context: map genre_id→вес (только позитив),
  genre_id→локализованное имя (через существующий механизм i18n переводов
  `catalog/i18n.py` + предзагруженные translations), set совпавших franchise_ids.
- Serializer (`RecommendationSerializer`): пересечение genres тайтла с
  позитивными весами, сортировка по весу desc, топ-3 имён; `franchise=true`
  если франшиза тайтла в set.

### Frontend

**5. lib/recommendations.ts**

- Типы: `reasons` в `Recommendation`.
- Мутации по паттерну lib/library.ts (`getCsrfToken()` + `X-CSRFToken`,
  credentials same-origin): `dismissRecommendation(slug)` POST,
  `undismissRecommendation(slug)` DELETE; 401/403 → null.

**6. recommendations-view.tsx**

- Вместо сырого скора — строка причин под карточкой:
  `По вашим жанрам: Драма, Комедия` + `Из вашей франшизы` (ключи RU/EN,
  словарь dictionaries.ts; ключ `recommendations.score` удалить).
- Кнопка «Не интересно» в строке под карточкой (видима всегда — touch-friendly,
  цель ≥40px по высоте, subtle secondary-стиль). Гостю не рендерится.
- Сценарий dismiss: клик → POST → карточка удаляется из списка; появляется
  инлайн-уведомление (существующие empty-state/panel стили, без нового
  toast-компонента): «Скрыто» + кнопка «Отменить», автоисчезание ~6 c.
  Отмена → DELETE → карточка возвращается на исходный индекс текущего списка.
  Ошибка сети → карточка остаётся, показывается `common.error`-текст.
- Полка на `/account` (recommendation-shelf.tsx) — без изменений в этой итерации.

### Документация

**7. IMPLEMENTATION_STATUS.md** — новый раздел по конвенции репозитория
(что изменилось, проверка, миграция, точки отката).

## Тесты

Backend (library/tests.py, расширить существующие recommendations-кейсы):
- dismissal: exclude из выдачи, restore после DELETE, auth/CSRF required,
  idempotent POST, 404 на чужой slug;
- негативные веса: дропнутый жанр опускает/убирает кандидата; только негативные
  сигналы → cold-start fallback, не пусто;
- масштабируемый франшизный бонус: монотонность по числу записей;
- полностью просмотренный тайтл (эпизоды есть, все watched, библиотеки нет) — отсутствует;
- tie-break: при равных скорах выше тайтл с большим rating_avg;
- reasons: корректные локализованные жанры и franchise-флаг.

Frontend (unit по конвенции vitest-тестов lib/components):
- типы/клиент: dismiss/undismiss формируют правильные запросы и обрабатывают 401/403;
- i18n: новые ключи присутствуют в RU и EN (паттерн существующего теста словаря).

## Валидация

- `cd backend && python3 -m pytest`; ruff; mypy; `makemigrations --check` до/после осознанной миграции.
- `cd frontend && npm run lint && npm run typecheck && npm test && npm run build`.
- `sh scripts/validate.sh`.
- UI-сценарий вручную недоступен без browser surface (см. design-qa.md) — отметить.

## Риски / заметки

- Полностью просмотренный ongoing-тайтл исчезает из рекомендаций — осознанно:
  возобновление покрывает ContinueWatching, рекомендации про новое.
- Исключения через id-сеты Python-side — bounded запросами; при росте каталога
  заменить на Subquery без изменения контракта API.
- Миграция expand-only, откат образов безопасен.
- Не входит в scope: un-dismiss UI вне снекбара, настройки скрытых тайтлов,
  коллаборативная фильтрация, Premium-гейтинг, причины на полке `/account`.
