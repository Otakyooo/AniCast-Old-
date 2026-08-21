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

## Контентная админка и аудит

- Django admin доступен на `/staff/` только staff-пользователям;
- тайтлы редактируются вместе с эпизодами, эпизоды — вместе с источниками;
- доступны жанры, франшизы, даты расписания и availability источников;
- аккаунты и staff permissions управляются через адаптированный email-based UserAdmin;
- external identities, Telegram challenges, библиотеки и история доступны в read-only режиме;
- создание, изменение и удаление контента фиксируются встроенным `django_admin_log`;
- admin static assets собираются в Docker image и отдаются через WhiteNoise;
- production включает HTTPS redirect, HSTS, proxy SSL detection и clickjacking protection.
- production-аккаунту владельца выданы staff и superuser permissions; доступ работает через обычную Telegram-сессию без отдельного пароля.
- `/staff/login/` перенаправляет на общую `/login` с email и Telegram bot confirmation;
- после успешного входа безопасный локальный `next=/staff/` возвращает пользователя прямо в админку;
- внешние и protocol-relative return URL не принимаются.

## Жалобы на источники

- авторизованный пользователь может отправить жалобу со страницы эпизода;
- причины: недоступность, неверный контент, региональная блокировка, качество и другое;
- комментарий ограничен 500 символами и обязателен для причины «Другое»;
- открытая жалоба с тем же источником и причиной не дублируется;
- создание жалоб ограничено `10/hour` на пользователя;
- пользовательский API возвращает только собственные жалобы;
- staff-очередь доступна в `/staff/` со статусами новая, на проверке, решена и отклонена;
- admin actions записывают обработчика, время и audit log entry.

## Providers и права

- добавлен provider registry с enabled-флагом и allowlist HTTPS-хостов;
- существующие источники мигрируются к disabled providers без автоматического права просмотра;
- прямой `Source.url` удалён из всех публичных serializers;
- rights grant привязан к конкретному источнику, имеет обязательный интервал и contract reference;
- одновременно допускается только один active grant на источник;
- playback endpoint работает fail closed и повторно проверяет provider, availability, approved grant, срок и hostname;
- activation и revocation выполняются audited admin actions;
- frontend показывает «Открыть у провайдера» только при `playback_available=true`.

## Франшизы

- публичные API `/api/v1/franchises/` и `/api/v1/franchises/<slug>/`;
- страницы `/franchises` и `/franchises/<slug>`;
- редакторский порядок учитывает `sort_order`, затем название;
- detail показывает связанные тайтлы с жанрами и ведёт на карточки;
- блок франшизы на странице тайтла стал ссылкой.

## Личные заметки

- приватный CRUD `/api/v1/notes/` и `/api/v1/notes/<slug>/`;
- одна заметка до 2000 символов на пользователя и тайтл;
- заметка не зависит от наличия тайтла в библиотеке;
- пустой текст и чужие заметки недоступны;
- редактирование доступно на странице тайтла, список — на `/notes`;
- заметки отображаются staff только read-only.

## Telegram-уведомления

- уведомления вынесены в отдельный `@anicast_push_bot`; auth bot не используется для рассылок;
- авторизованный пользователь создаёт одноразовый challenge и подтверждает привязку через `/start` второго бота;
- notification token, username, webhook URL и secret полностью отделены от auth-контура;
- `/stop` отключает канал без удаления аккаунта;
- на странице тайтла доступна подписка на новые эпизоды;
- Celery Beat запускает доставку каждые 15 минут;
- delivery ledger с unique constraint предотвращает повторную отправку одного эпизода одной подписке;
- неуспешная доставка повторяется не более трёх раз, блокировка бота отключает канал;
- каналы, подписки, challenges и доставки доступны staff для диагностики.

## Мониторинг источников

- Celery Beat проверяет enabled provider sources каждые 10 минут;
- URL обязан быть HTTPS, входить в provider allowlist и резолвиться только в public global IP;
- private/reserved адреса и redirects отклоняются до изменения состояния;
- сохраняются HTTP status, latency, ошибка и история проверок;
- после трёх последовательных сбоев выставляется `provider_error` и playback немедленно закрывается;
- успешная проверка восстанавливает только автоматически выставленный `provider_error`;
- ручные `unavailable`, `geo_blocked` и `expired` мониторинг не перезаписывает;
- диагностика и история доступны в `/staff/`.

## Импорт контента

- management command `import_catalog <file.json>` валидирует genres, franchises, providers, titles, episodes и sources;
- режим по умолчанию — dry-run с полной транзакцией и rollback;
- запись требует явного `--apply`;
- неизвестные связи, дубли эпизодов, неверные даты/choices и HTTP source URL отклоняются;
- импортированные providers остаются disabled и не получают rights grants автоматически;
- apply выполняется атомарно и безопасен для повторного запуска через update-or-create.

## CI

- GitHub Actions проверяет backend tests, Ruff, mypy, migration drift и Django checks;
- frontend проходит clean `npm ci`, lint, typecheck и production build;
- infrastructure job валидирует оба Compose-файла, Docker images и Caddyfile;
- workflow запускается на push и pull request с read-only repository permissions.

## Мультиязычный контент

- переводы хранятся отдельно для жанров, франшиз, тайтлов и эпизодов;
- поддерживаются `ru`, `en`, `uk`, `be`, `kk`, `de`, `fr`, `es`, `it`, `ja`, `ko`, `zh`;
- русский язык используется по умолчанию, английский — обязательный fallback для существующего каталога;
- API принимает `?lang=`, cookie `anicast_lang` и `Accept-Language`;
- поиск работает по базовым и переведённым названиям;
- frontend получил постоянный переключатель RU/EN;
- admin содержит русскоязычные inline-блоки переводов и выбор языка;
- data migration переносит существующие значения в English translations и добавляет русские названия распространённых жанров;
- seed создаёт RU/EN версии demo-контента;
- JSON import поддерживает объект `translations` и валидирует языковые коды.

## Мультиязычный интерфейс

- весь основной frontend переведён через единый типизированный RU/EN dictionary;
- локализованы навигация, metadata, auth, account, catalog, schedule, franchises и страницы тайтлов;
- локализованы client states библиотеки, истории, заметок, жалоб, playback и Telegram notifications;
- `<html lang>`, `Intl.DateTimeFormat` и даты заметок соответствуют выбранному языку;
- `preferred_language` хранится в аккаунте и синхронизируется между устройствами;
- анонимный выбор хранится в безопасной cookie `anicast_lang`;
- после email/Telegram login cookie синхронизируется с настройкой пользователя;
- push-бот формирует RU/EN сообщение и использует переведённые название тайтла и эпизода;
- пользовательские client-side ошибки имеют английский fallback вместо русских backend messages.

## Проверки

Последний полный локальный прогон:

- backend: `49 passed`;
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
- anonymous и обычные пользователи не получают доступ к `/staff/`;
- staff-операции с контентом создают audit log entry;
- admin static CSS доступен в production image.
- жалобы изолированы по пользователю, защищены от открытых дублей и обрабатываются audited staff actions.
- production smoke подтверждает создание жалобы, HTTP 400 для дубля, приватный список и CSRF Origin enforcement.
- production owner flow подтверждает цепочку `/staff/` → Telegram challenge → staff session → `/staff/` HTTP 200 → logout.
- multi-slice smoke подтверждает fail-closed legacy sources, approved playback gate без URL в catalog payload, franchise list/detail и приватный CRUD заметок.
- notification smoke подтверждает отдельный webhook secret, challenge link, active channel, подписку, `/stop`, Celery task registration и каскадную очистку.
- monitoring/import smoke подтверждает private DNS rejection, автоматический `provider_error` после трёх сбоев, dry-run rollback, atomic apply и disabled provider без grants.
- content i18n smoke подтверждает default RU, explicit EN, cookie-based SSR, поиск по русскому названию и русские translation inlines в staff.
- full UI i18n smoke подтверждает RU/EN navigation, pages, metadata, account preference API и английский Telegram push template с переведённым контентом.

## Следующие задачи

- provider-specific adapters и короткоживущие playback URL;
- embed/callback прогресса для провайдеров, которые разрешают такую интеграцию;
- мониторинг ошибок, метрики и автоматизированный rollback;
- персонажи, заметки, community и moderation;
- уведомления, рекомендации и Premium.

## Ограничения

- точная позиция просмотра не реализована без доверенного callback от провайдера;
- источники не запускаются, пока не определены права и разрешённый способ интеграции;
- Telegram bot token и webhook secret должны храниться только в игнорируемом production `.env`;
- для первого входа в `/staff/` требуется отдельно создать superuser с сильным уникальным паролем;
- test suite использует SQLite, а критический Telegram polling flow дополнительно проверяется production smoke-тестом на PostgreSQL.
