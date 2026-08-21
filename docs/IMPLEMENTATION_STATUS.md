# AniCast — статус реализации

Дата: 21 августа 2026

## Production

- сайт: `https://anicast.online`;
- frontend: Next.js 15 на VPS за Caddy;
- backend: Django 5.2 + DRF на MainServer;
- backend доступен с VPS через AmneziaWG по `10.78.0.2:8000`;
- PostgreSQL, Redis, Celery worker и Celery Beat запущены через Docker Compose;
- Caddy маршрутизирует `/api/*` на MainServer, остальные запросы — на Next.js;
- readiness проверяет PostgreSQL и Redis;
- перед миграциями создаются локальные PostgreSQL backups в `backups/`.

## Discovery

- каталог `/catalog` с поиском, фильтрами и пагинацией;
- API `/api/v1/titles/` и детальная выдача по slug;
- жанры, франшизы, эпизоды и статусы источников;
- отдельные страницы тайтла и эпизода;
- unavailable, geo-blocked, expired и provider-error источники показываются честно, без фиктивного playback;
- deterministic demo seed через `python manage.py seed_catalog`.

## Аккаунты

- email-регистрация и вход;
- Django cookie sessions, Secure/HttpOnly cookies и CSRF-защита;
- проверка сложности пароля и rate limiting auth endpoints;
- страницы `/login`, `/register` и `/account`;
- email может отсутствовать у аккаунта, созданного через внешний identity provider;
- внешние identity хранятся отдельно от основной модели пользователя.

### Telegram

- legacy Telegram Login Widget удалён из пользовательского потока;
- вход выполняется подтверждением через `@anicast_auth_bot`, без ввода номера на сайте;
- сайт создаёт одноразовый challenge сроком на пять минут;
- challenge хранится в БД только как SHA-256 hash и привязывается к браузерной Django-сессии;
- пользователь открывает deep link `t.me/<bot>?start=<challenge>` и нажимает Start;
- Telegram webhook защищён отдельным `X-Telegram-Bot-Api-Secret-Token`;
- webhook подтверждает Telegram identity, браузер получает сессию через polling;
- challenge имеет состояния pending, approved, consumed и expired;
- повторное использование, истёкший challenge и попытка завершения из другого браузера отклоняются;
- production webhook зарегистрирован на `/api/v1/auth/telegram/webhook/`.

## Личная библиотека

- приватный API `/api/v1/library/`;
- страница `/library`;
- статусы: смотрю, запланировано, просмотрено, отложено и брошено;
- избранное хранится независимо от статуса;
- добавление, изменение и удаление доступны со страницы тайтла;
- библиотека изолирована по пользователю и синхронизируется через серверную сессию.

## История эпизодов

- отдельная страница `/history`;
- открытие страницы эпизода создаёт подтверждённую запись истории;
- пользователь может явно отметить эпизод просмотренным и снять отметку;
- повторное открытие не сбрасывает watched-state;
- главная показывает блок «Недавно открывали» только авторизованному пользователю;
- точный таймкод не имитируется и не сохраняется без подтверждённого provider callback.

## Расписание

- публичная страница `/schedule` и API `/api/v1/schedule/`;
- режимы «Сегодня» и «7 дней»;
- эпизоды группируются по подтверждённой `air_date` и ведут на страницу серии;
- точное время не показывается, пока источник данных хранит только дату;
- произвольный API-диапазон ограничен 31 днём;
- неверный формат, обратный и слишком большой диапазон возвращают контролируемый HTTP 400.

## Проверки

Последний полный локальный прогон:

- backend: `27 passed`;
- Ruff: без ошибок;
- mypy: без ошибок в 50 source files;
- Django system check: без ошибок;
- `makemigrations --check --dry-run`: изменений нет;
- frontend lint: без warnings и errors;
- frontend typecheck: успешно;
- frontend production build: успешно;
- `git diff --check`: успешно.

Production smoke-check подтверждает:

- публичные страницы и API отвечают;
- регистрация, cookie session, библиотека и история работают end-to-end;
- расписание и его API доступны публично;
- Telegram challenge возвращает pending до подтверждения;
- неверный webhook secret отклоняется;
- webhook approval создаёт identity;
- challenge завершается только в исходной браузерной сессии;
- после завершения `/auth/me/` возвращает авторизованного пользователя;
- Telegram сообщает healthy webhook status без last error.

## Следующие задачи

- provider adapter и rights registry;
- разрешённый внешний playback или embed с callback прогресса;
- контентная админка и аудит изменений;
- жалобы на недоступные источники;
- мониторинг ошибок, метрики и автоматизированный rollback;
- персонажи, заметки, community и moderation;
- уведомления, рекомендации и Premium.

## Ограничения

- точная позиция просмотра не реализована без доверенного callback от провайдера;
- источники не запускаются, пока не определены права и разрешённый способ интеграции;
- Telegram bot token и webhook secret должны храниться только в игнорируемом production `.env`;
- test suite использует SQLite, а критический Telegram polling flow дополнительно проверяется production smoke-тестом на PostgreSQL.
