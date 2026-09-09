# Техническая зрелость Anicast

Оценка на 09.09.2026 по исходникам, конфигурации и сохранённым production-проверкам.
Это инженерная оценка малого production-сервиса, а не внешний пентест или SLA.

Стек современный и пригоден для развития. Сильнее всего продвинулись эксплуатация,
изоляция фоновых задач и проверяемость восстановления. Главные ограничения —
обновление зависимостей, единичные хосты и недостаточно измеренная нагрузочная
ёмкость. Количество фреймворков само по себе зрелость не повышает.

## Технологии и поддержка

| Слой | Зафиксировано в проекте | Оценка |
| --- | --- | --- |
| Frontend | Next 15.5.23, React 19.1.1, TypeScript 5.9.2 strict, App Router | Современная основа; Next 15 уже Maintenance LTS |
| Backend | Python 3.12, Django 5.2.17, DRF 3.17.2, Gunicorn | Поддерживаемая LTS-основа, модульный монолит соответствует размеру системы |
| Данные | PostgreSQL 17, Redis 7 в трёх ролях | Зрелые инструменты; изоляция есть, репликации/автоматического failover нет |
| Фоновые задачи | Celery 5.5.3, два workers по одному процессу | Нагрузка ограничена; рост очереди требует измерений перед увеличением concurrency |
| Развёртывание | Docker Compose, Caddy, AWG, CI/GHCR digests | Воспроизводимые образы и откат; топология и хосты ещё требуют ручной эксплуатации |
| Наблюдение | Prometheus, Alertmanager, blackbox, node-exporter | Есть реальные проверки API, Redis, ресурсов и свежести внешних копий |

Версии взяты из [package.json](../frontend/package.json),
[requirements](../backend/requirements.txt), Dockerfiles и Compose.
Django 5.2 LTS поддерживается до апреля 2028; переход на новый major только ради
новизны не требуется. [Официальный график Django](https://www.djangoproject.com/download/).
PostgreSQL 17 поддерживается до 08.11.2029; patch-релизы внутри ветки всё равно
нужно поддерживать. [Политика PostgreSQL](https://www.postgresql.org/support/versioning/).

Next 16 — Active LTS, Next 15 — Maintenance LTS. По опубликованному правилу
«два года от первого major release» и дате 21.10.2024 окно Next 15 заканчивается
21.10.2026; это вывод из политики, который надо перепроверить перед миграцией.
[Политика Next.js](https://nextjs.org/support-policy).

## Что уже подтверждено

- Backend/frontend/infrastructure gates и публикация образов прошли в
  [CI 34291367680](https://github.com/Otakyooo/AniCast/actions/runs/34291367680).
  Frontend имеет 73 unit tests для логики, lint/typecheck/build; это не браузерный E2E.
- Broker, control и ephemeral Redis изолированы; eviction/outage проверены на
  disposable среде. Оба workers проверяются отдельно.
- Nonce CSP, закрытые служебные порты, отдельная monitoring network, ограничение
  ресурсов, frontend от node, session/CSRF/permissions и ограниченные API-запросы.
- DB/media восстанавливались на другом хосте; login/reset/captured notifications/
  signed playback и private proxy switch/rollback прошли. 142.16s — время самой
  репетиции, не полного восстановления после аварии. [Доказательства](archive/releases/RELEASE-2026-09-09-hardening.md).
- Новый OAuth проверен forced refresh на двух машинах; свежий dump и age kits
  независимо скачаны из Drive и сверены. [Проверки](archive/releases/RELEASE-2026-09-09-oauth.md).

## Обнаруженный долг

### Обновления безопасности — первый приоритет

Во время этой проверки `npm audit --json` для текущего lockfile сообщил о трёх
пакетах: Next — critical, sharp и js-yaml — high. Это число затронутых пакетов,
не число независимых эксплуатируемых уязвимостей сайта. `js-yaml` относится к
dev dependencies; Next/sharp входят в production dependency graph.

- Next 15.5.23 входит в диапазоны двух advisories. Один касается Windows hosting,
  тогда как production использует Linux/Alpine.
  [Advisory Windows](https://github.com/vercel/next.js/security/advisories/GHSA-p293-qw3h-jr36).
- Другой относится к AVIF input в image optimizer и библиотеке libheif/sharp.
  Формат ответа WebP не доказывает недостижимость обработки AVIF input. Эксплуатация
  именно на текущем musl-контейнере этим аудитом не проверена.
  [Advisory image optimizer](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4).
- В проекте принудительно закреплён sharp 0.35.0; исправленная ветка начинается
  с 0.35.4. Одного обновления Next недостаточно, если оставить старый override.
  [Advisory sharp](https://github.com/lovell/sharp/security/advisories/GHSA-rgj7-g3m4-5g8c).
- npm предлагает Next 15.5.25 без смены major; требуется также исправить sharp
  override и обновить js-yaml, проверить lockfile, сборку musl image и реальные постеры.
  `eslint-config-next` 15.4.6 расходится с Next 15.5.23 — инструменты стоит согласовать.

CI запускает `pip-audit`, но явного npm audit gate в workflow нет. Dependabot и
успешный build не заменяют такой gate. Обновление runtime-зависимостей и его
выкладка не выполнялись в этой уборке документации; проблема остаётся открытой.

### Отказоустойчивость и ёмкость

MainServer и домашний интернет/питание находятся на пути API. Единственный VPS
тоже остаётся точкой отказа. Есть восстановление из копии, но нет автоматического
переключения на актуальную реплику. RPO 6h/24h и RTO 2h — условные цели из runbook.
Перенос data tier на внешний хост уберёт домашнюю зависимость, но сам по себе не
создаст HA без второй реплики и проверки failover.

Владелец позже увеличит только RAM MainServer до 4 ГБ; CPU остаётся прежним.
За сутки наблюдались активный swap и минимум 459 MiB доступной памяти. Последний
измеренный час был спокойнее, но нагрузочный предел, число одновременных зрителей
и сезонный пик неизвестны. [Измерения](archive/releases/RELEASE-2026-09-09-capacity.md).

### Проверяемость и сопровождаемость

Frontend strict typing включён, backend mypy — `strict=False` и
`ignore_missing_imports=True`; считать весь backend строго типизированным нельзя.
Браузерная проверка была ручной, полный mobile/screen-reader набор не подтверждён.
Нужны воспроизводимые E2E ключевых сценариев и нагрузочный профиль. Не следует
считать SQLite-тесты полной проверкой поведения PostgreSQL.

Python dev/test инструменты устанавливаются в тот же backend image, что production
зависимости. Разделение requirements и стадий сборки может уменьшить образ и
поверхность зависимостей; сначала сохранить идентичность runtime-набора и CI.

Приоритет: security patch и npm gate → поддерживаемая ветка Next → E2E/нагрузка →
внешний data host и проверенный план отказа. Полная смена Django/Next, Kubernetes
или дробление на микросервисы сейчас не обоснованы измеренной потребностью.
