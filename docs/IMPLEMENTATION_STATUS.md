# AniCast — статус реализации

Дата: 22 августа 2026

## Production

- сайт: `https://anicast.online`;
- frontend: Next.js 15 на VPS за Caddy;
- backend: Django 5.2 + DRF на MainServer;
- backend доступен с VPS через AmneziaWG по `10.78.0.2:8000`;
- PostgreSQL, Redis, Celery worker и Celery Beat запущены через Docker Compose;
- Caddy маршрутизирует `/api/*` на MainServer, остальные запросы — на Next.js;
- readiness проверяет PostgreSQL и Redis.

## Observability и rollback

Backend с observability-кодом развёрнут в production (2026-08-22): миграции применены, `/internal/metrics` отвечает за bearer token:

- backend пишет безопасные JSON-логи с request ID и bounded operational fields;
- приватный `/internal/metrics` требует bearer token, доступен только через MainServer listener и не маршрутизируется публичным Caddy;
- Compose healthchecks покрывают PostgreSQL, Redis, readiness backend, Celery worker/Beat, frontend и Caddy;
- deploy/rollback scripts используют immutable image digest, `current/previous` manifests, smoke/readiness gates и image-only automatic rollback.

## Мониторинг и алерты

Стек `infra/monitoring` запущен на MainServer (2026-08-22):

- Prometheus v3.14 (retention 15d) скрейпит backend через nginx-sidecar с заголовком `X-Forwarded-Proto` внутри docker-сети `mainserver_internal`;
- Alertmanager v0.34 с нативным Telegram-ресивером, node-exporter, все сервисы memory-limited (~110 MiB на весь стек);
- 13 alert-правил: недоступность backend, рост 5xx, сбои Celery-задач, provider check failures, сбои доставки уведомлений, disk <15%/<7%, RAM <10%, self-checks мониторинга, недоступность публичного сайта снаружи (blackbox) и метрики хоста VPS;
- blackbox-пробы сайта и API идут из интернета; node-exporter на VPS привязан к AWG-интерфейсу;
- все публичные SSR-страницы деградируют корректно при недоступном API (проверено контролируемой остановкой backend: 9 страниц → 200 с заглушками, API → 502, алерты не шумят);
- UI Prometheus/Alertmanager доступны только на `127.0.0.1` MainServer через SSH port forwarding;
- `scripts/validate.sh` проверяет compose/promtool/amtool конфигурацию мониторинга.

## Бэкапы PostgreSQL

Автоматизация включена (2026-08-22):

- `scripts/backup-db.sh`: verified `pg_dump -Fc` дамп, retention 14 дневных + 8 недельных, шифрованная офсайт-копия на Google Drive (rclone crypt, OAuth-токен пользователя);
- `scripts/restore-db.sh`: безопасная проверочная реставрация в scratch-БД (`--verify`) и полный restore (`--force`) с подтверждением и стопом приложения;
- cron: ежедневный бэкап 03:15, воскресная проверочная реставрация 04:30;
- при сбое бэкапа скрипт отправляет Telegram-уведомление через ops-бота из `infra/monitoring/.env`;
- тесты выполнены: полный roundtrip локально + шифрованная выгрузка в Google Drive + scratch-реставрация (43 таблицы).

## Публикация образов

- `.github/workflows/publish.yml` пушит `anicast-backend` и `anicast-frontend` в GHCR на каждый push в `main` и теги `v*`, в summary печатает digest-строки для release-манифестов;
- `scripts/release-manifest.sh` резолвит теги в immutable digest и печатает manifest'ы для `deploy.sh`;
- пакеты приватные: хостам для pull нужен `docker login ghcr.io` с PAT `read:packages`;
- production MainServer и VPS работают на digest-pinned образах из GHCR (с 2026-08-22); релиз-переключение и откат описаны в OPERATIONS.md.

## Каталог: производительность и постеры

- `playback_available` считается пакетным prefetch источников, провайдеров и активных approved grants: детальная выдача тайтла больше не делает по два SQL-запроса на каждый источник (регрессионный тест ограничивает 12 эпизодов с источниками 10 запросами);
- `/api/v1/titles/<slug>/` пагинирует эпизоды (`episodes_page`, `episodes_page_size`, по умолчанию 20, максимум 50) и отдаёт полное число в `episodes_count`;
- страница эпизода использует отдельный `/api/v1/titles/<slug>/episodes/<number>/` вместо загрузки всех эпизодов тайтла;
- фронтенд показывает пагинацию списка эпизодов и считает количество по `episodes_count`;
- `fetch_shikimori` берёт максимальное разрешение постера MAL (`maximum_image_url` с fallback на `large_image_url`);
- `backfill_posters` заменяет мыльные Shikimori-постеры и пустые значения на максимальный MAL-арт: dry-run по умолчанию, запись через `--apply`, безопасен для повторного запуска.

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

## Каталог: импорт метаданных Shikimori

- `fetch_shikimori` + `import_catalog`: топ-100 популярности импортирован в production (2026-08-22) — 100 тайтлов, 31 жанр, 4474 эпизода, RU/EN переводы, японские оригиналы, постеры;
- импорт идемпотентен, dry-run по умолчанию, источников воспроизведения не создаёт (права не затронуты);
- постеры рендерятся на карточках каталога и страницах тайтлов (next/image + fallback-плейсхолдер);
- runbook в OPERATIONS.md.

## VPS firewall

- ufw включён (2026-08-22): публично открыты только TCP 22/80/443 и UDP 443 (AmneziaWG); трафик awg0 разрешён целиком — MainServer транзитит интернет через туннель.

## Каталог v2: франшизы и персонажи

- `fetch_shikimori` группирует франшизы по slug из деталей аниме (head — самый ранний тайтл) и подтягивает персонажей: GraphQL `characterRoles` (Main → protagonist, прочее → supporting) + REST-детали (русская биография, японское имя, портрет);
- `import_catalog` расширен секцией `characters` и привязками `titles[].characters` (валидация ролей/дублей/ссылок, идемпотентный apply);
- страницы персонажей рендерят портреты через next/image с fallback на букву;
- импортировано в production (2026-08-22): 74 франшизы, 691 персонаж, 800 связей тайтл-персонаж; у всех 100 тайтлов есть персонажи, у 96 — франшиза.

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
- provider явно выбирает зарегистрированный playback adapter; отсутствующий или неизвестный adapter закрывает playback;
- нейтральный `external_link` adapter не имитирует API поставщика и не принимает credentials/config;
- API сохраняет контракт `mode + url`, но выдаёт подписанный внутренний URL с TTL 60 секунд вместо постоянного `Source.url`;
- при открытии короткоживущего URL заново проверяются source, enabled provider, adapter и active approved grant;
- token не содержит target URL или credentials, а redirect разрешён только на точный HTTPS hostname из allowlist;
- playback и redirect responses имеют `no-store`, redirect также запрещает передачу referrer;
- activation и revocation выполняются audited admin actions;
- admin и import отклоняют неизвестные adapters, credential config, private/reserved IP hosts и source URL вне allowlist;
- frontend показывает «Открыть у провайдера» только при `playback_available=true` и принимает только same-origin playback URL.

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
- сохраняются HTTP status, latency, безопасный bounded error code и история проверок;
- после трёх последовательных сбоев выставляется `provider_error` и playback немедленно закрывается;
- успешная проверка восстанавливает только автоматически выставленный `provider_error`;
- ручные `unavailable`, `geo_blocked` и `expired` мониторинг не перезаписывает;
- диагностика и история доступны в `/staff/`.

## Импорт контента

- management command `import_catalog <file.json>` валидирует genres, franchises, providers, titles, episodes и sources;
- режим по умолчанию — dry-run с полной транзакцией и rollback;
- запись требует явного `--apply`;
- неизвестные связи, дубли эпизодов, неверные даты/choices и HTTP source URL отклоняются;
- импортированные providers требуют явный playback adapter, остаются disabled и не получают rights grants автоматически;
- apply выполняется атомарно и безопасен для повторного запуска через update-or-create.

## CI

- GitHub Actions проверяет backend tests, Ruff, mypy, migration drift и Django checks;
- frontend проходит clean `npm ci`, lint, typecheck и production build;
- infrastructure job валидирует оба Compose-файла, Docker images и Caddyfile;
- CI валидирует shell deploy scripts, запрет публичного metrics route, Django deploy checks и whitespace diff;
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

## Персонажи

- multilingual Character и CharacterTranslation;
- связь персонажа с тайтлом хранит роль и редакторский порядок;
- публичные list/detail API и страницы `/characters`, `/characters/<slug>`;
- поиск работает по базовым и переведённым именам;
- detail показывает связанные тайтлы и локализованную роль;
- staff поддерживает переводы, связи с тайтлами и media inlines.

## Медиа

- изображения, трейлеры и промо связаны ровно с одним тайтлом или персонажем;
- опубликованный asset обязан иметь credit и `rights_reference`;
- drafts не возвращаются публичным API;
- captions поддерживают переводы;
- страница `/media` фильтрует опубликованные материалы по типу;
- staff управляет публикацией, атрибуцией, правами и переводами.

## Рекомендации

- приватный endpoint `/api/v1/recommendations/`;
- уже добавленные в библиотеку тайтлы исключаются;
- кандидаты ранжируются по пересечению жанров библиотеки;
- пустая библиотека получает безопасный fallback каталога;
- страница `/recommendations` показывает локализованные карточки и score причины.

## Сообщество

- пользователь может поставить одну оценку 1–10 каждому тайтлу и редактировать её;
- средняя оценка и количество голосов доступны публично;
- одна рецензия на пользователя/тайтл, длина 20–5000 символов;
- рецензия поддерживает spoiler flag и после каждого изменения возвращается в pending;
- публично выдаются только approved reviews;
- страница тайтла содержит рейтинг, форму рецензии и spoiler disclosure;
- `/community` показывает одобренные рецензии со ссылками на тайтлы;
- review mutations ограничены `5/hour` на пользователя;
- staff actions approve/reject записывают модератора, время публикации и audit log;
- рейтинги доступны staff read-only, удаление community records через admin запрещено.

## Пользовательские коллекции

- авторизованный пользователь создаёт до 50 именованных подборок по 200 тайтлов;
- коллекции имеют неизменяемый owner-scoped slug, описание и private/public visibility;
- элементы добавляются, удаляются и переставляются в атомарном плотном порядке;
- owner API изолирован по пользователю, а чужие и отсутствующие коллекции одинаково возвращают HTTP 404;
- публичная ссылка использует непрозрачный UUID владельца и не раскрывает email, внутренний ID или external identities;
- перевод public-коллекции в private немедленно закрывает публичную выдачу с `Cache-Control: no-store`;
- страницы `/collections`, `/collections/manage/<slug>` и публичный detail поддерживают RU/EN;
- со страницы тайтла можно добавить или удалить тайтл в собственных коллекциях;
- Django admin показывает коллекции и элементы только для диагностики без изменения пользовательских данных.

## Design shell v0.3 — первая итерация

- `AniCast_Design_Technical_Spec_v0.3.docx` разобран вместе с четырьмя визуальными референсами;
- desktop sidebar полностью удалён из фактической оболочки;
- добавлен sticky TopNav: logo, основные routes, global search, notifications и account controls;
- primary navigation ограничена Главной, Каталогом, Расписанием, Франшизами и Персонажами;
- Media, Community, Library и Recommendations перенесены в overflow «Ещё»/профильный контекст;
- active state использует яркий текст и нижний primary indicator 2 px без фоновой таблетки;
- content ограничен 1600 px с адаптивными gutters 32/24/16 px;
- grid density следует 6/5/4/2 карточкам по breakpoint;
- mobile использует compact app bar и fixed bottom navigation из пяти действий;
- добавлены design tokens Background/Surface/Elevated/Border/Primary/Success/Warning/Danger из freeze;
- typography переведена на Inter/system stack, focus ring — `#9D87FF`;
- глобальный hero получил desktop/mobile геометрию и нейтральный art-ready gradient fallback;
- account route подключён к общей shell вместо отдельного auth-like экрана;
- motion учитывает `prefers-reduced-motion`;
- auth/register остаются отдельными экранами намеренно.

## Design shell v0.3 — вторая итерация

- рамка страницы вынесена в единый `PageShell`: он владеет глобальной навигацией, mobile bottom nav, шириной контента, back-ссылкой и заголовком страницы;
- все 18 маршрутов перестали собирать оболочку вручную; убран мёртвый `topbar`, который на desktop скрывался через `display:none`, но всё равно рендерил второй `AccountLink` с переключателем языка в каждом HTML-ответе;
- `Sidebar` переименован в `SiteHeader` — компонент рисует TopNav, а desktop sidebar удалён ещё в первой итерации;
- `shell.css` и `shell-overrides.css` слиты в `globals.css`: устранены правила, которые отменяли друг друга (`.more-nav` display none → flex, `.topbar` display flex → none), CSS-переменные gutter вынесены в токены;
- восстановлены отсутствовавшие стили: `episode-list`, `episode-card`, `episode-heading`, `episode-number`, `episode-sources`, `source-list`, `source-status` с цветовой индикацией доступности и `franchise-panel` — раньше эти классы рендерились без единого CSS-правила;
- источники на странице тайтла получили статусную индикацию по левой границе: доступен (success), регион (warning), ошибка провайдера (danger);
- добавлены глобальные `app/error.tsx` и `app/not-found.tsx`; раньше `error.tsx` существовал только для `/catalog` и `/titles/[slug]`, а 404 отдавался дефолтным экраном Next.js;
- поиск на странице персонажей и каталога переведён в собственные поля формы вместо скрытого topbar-поиска;
- у расписания появилось активное состояние переключателя «Сегодня»/«7 дней»;
- skeleton-состояния каталога и тайтла переведены на ту же оболочку, поэтому при загрузке навигация больше не исчезает.

## Проверки

Последний полный локальный прогон:

- backend: `109 passed`;
- Ruff: без ошибок;
- mypy: без ошибок в 100 source files;
- Django system check и `check --deploy`: без ошибок;
- `makemigrations --check --dry-run`: изменений нет;
- frontend lint: без ESLint errors; Next.js сообщил только deprecation/workspace-root warnings;
- frontend typecheck: успешно;
- frontend production build: успешно;
- `git diff --check`: успешно.
- оба Compose config, shell syntax, Caddyfile и запрет public metrics route: успешно;
- hermetic deploy failure test подтвердил automatic rollback на previous VPS manifest;
- backend и frontend Docker images: успешно собраны.

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
- discovery smoke подтверждает RU/EN character detail, role links, draft media filtering, rights-attributed published media и genre-ranked recommendations с исключением библиотеки.
- community smoke подтверждает rating bounds, pending privacy, approval publication, spoiler flag и обязательный reset в moderation queue после edit.
- design shell smoke подтверждает TopNav/mobile bottom nav, отсутствие desktop sidebar, RU/EN navigation, profile shell и HTTP 200 всех основных routes.

## Следующие задачи

- embed/callback прогресса для провайдеров, которые разрешают такую интеграцию;
- персонажи, заметки, community и moderation;
- уведомления, рекомендации и Premium.

## Ограничения

- точная позиция просмотра не реализована без доверенного callback от провайдера;
- источники не запускаются, пока не определены права и разрешённый способ интеграции;
- Telegram bot token и webhook secret должны храниться только в игнорируемом production `.env`;
- для первого входа в `/staff/` требуется отдельно создать superuser с сильным уникальным паролем;
- test suite использует SQLite, а критический Telegram polling flow дополнительно проверяется production smoke-тестом на PostgreSQL.
- metrics counters хранятся в Redis и могут сброситься при потере Redis; endpoint не заменяет внешний alert evaluator;
- автоматический rollback откатывает только application images и требует backward-compatible expand/contract migrations; restore PostgreSQL — осознанная ручная операция по runbook из OPERATIONS.md (автоматизируемая проверка scratch-реставрацией включена в cron);
- rclone на MainServer использует shared client_id Google Drive — при его отключении нужно создать project-owned OAuth client и переавторизоваться;
- формальный пайплайн `deploy.sh` в production ещё не выполнялся: хосты используют digest-switch через compose (runbook в OPERATIONS.md), автоматический image-only rollback не подключён.
