# Техническая зрелость Anicast

Оценка на 09.09.2026 по исходникам, конфигурации и сохранённым production-проверкам.
Это инженерная оценка малого production-сервиса, а не внешний пентест или SLA.

Стек современный и пригоден для развития. Сильнее всего продвинулись эксплуатация,
изоляция фоновых задач и проверяемость восстановления. Главные ограничения —
единичные хосты, неполное сценарное E2E и недостаточно измеренная нагрузочная
ёмкость. Количество фреймворков само по себе зрелость не повышает.

## Технологии и поддержка

| Слой | Зафиксировано в проекте | Оценка |
| --- | --- | --- |
| Frontend | Next 16.3.4, React 19.2.8, TypeScript 5.9.2 strict, App Router | Переход на Next 16 выполнен; Turbopack и Node proxy проверены в CI/runtime |
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

Переход с Next 15 на Next 16 выполнен 09.09.2026. Контракт nonce/CSP, SSR,
image cache и лимиты слабого VPS сохранены. [Решение](architecture/006-next16.md).
При дальнейших обновлениях проверять [политику поддержки Next.js](https://nextjs.org/support-policy).

## Что уже подтверждено

- Backend/frontend/infrastructure gates и публикация образов прошли в
  [CI 34347560556](https://github.com/Otakyooo/AniCast/actions/runs/34347560556).
  Frontend имеет 73 unit tests, lint/typecheck/build и 16 Chromium E2E проверок
  общего каркаса: темы, storage, контраст, логотип, nonce/no-store, доступность
  навигации и keyboard search на четырёх viewport.
  Это не полный E2E реального входа и плеера.
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

### Обновления безопасности — исправлено 09.09.2026

Выявленные advisories закрыты обновлением Next и eslint-config-next до 15.5.25,
sharp до 0.35.4, js-yaml до 4.3.2. `npm audit` текущего lockfile сообщил о нуле
уязвимостей, включая dev dependencies. CI теперь блокирует high/critical через
`npm run audit`; это проверка известных advisories на дату запуска.

Новый frontend развёрнут по digest. Проверены native sharp/libvips в Alpine image,
настоящий постер через production optimizer, главная, каталог и смена темы.
Первый холодный запрос постера был медленным; результаты и границы проверки
сохранены в [отчёте релиза](archive/releases/RELEASE-2026-09-09-frontend-security.md).
Следующим релизом Next обновлён до 16.3.4, React до 19.2.8, npm audit снова
прошёл без известных уязвимостей. [Релиз Next 16 и админки](archive/releases/RELEASE-2026-09-09-next16.md).

### Последовательность развёртывания — исправлено 09.09.2026

При релизе 09.09 Compose пересоздал API/default worker/beat, затем ждал завершения
старого bulk worker перед запуском новых контейнеров. API пришлось запустить
отдельно во время ожидания. Новый общий скрипт deploy/rollback запускает и проверяет
API перед workers; bulk имеет grace 1900s при hard limit 1800s. В Docker CI
получены 7 успешных ответов нового API до выхода старого worker; ошибки каждой
фазы проверены с откатом. Production прошёл все health gates. Один backend всё
ещё ненадолго недоступен при пересоздании; это не blue/green или HA.
[Решение](architecture/007-staged-rollout.md), [релиз](archive/releases/RELEASE-2026-09-09-staged-design.md).

### Отказоустойчивость и ёмкость

MainServer и домашний интернет/питание находятся на пути API. Единственный VPS
тоже остаётся точкой отказа. Есть восстановление из копии, но нет автоматического
переключения на актуальную реплику. RPO 6h/24h и RTO 2h — условные цели из runbook.
Перенос data tier на внешний хост уберёт домашнюю зависимость, но сам по себе не
создаст HA без второй реплики и проверки failover.

ОС MainServer уже видит 3606 MiB RAM; CPU остался один. В часу 10:03–11:03 UTC
доступная RAM была не ниже 2055.602 MiB, CPU busy (5m) — не выше 15.837%,
iowait — 0.615%, swap in/out — 0.156/0.226 pages/s. Все 13 отсчётов получены.
VPS по-прежнему имеет 961 MiB RAM; лимиты/concurrency не увеличивались.
Число одновременных зрителей и сезонный пик неизвестны. Прежние измерения до
увеличения RAM сохранены в [архиве](archive/releases/RELEASE-2026-09-09-capacity.md).

### Проверяемость и сопровождаемость

Frontend strict typing включён, backend mypy — `strict=False` и
`ignore_missing_imports=True`; считать весь backend строго типизированным нельзя.
Общий каркас уже имеет браузерный CI; полный mobile/screen-reader набор не подтверждён.
В 12 старых компонентах остаются 18 warnings `react-hooks/set-state-in-effect`;
остальные ошибки lint блокируют CI. Нужны сценарные E2E входа/плеера и нагрузочный профиль. Не следует
считать SQLite-тесты полной проверкой поведения PostgreSQL.

Python dev/test инструменты устанавливаются в тот же backend image, что production
зависимости. Разделение requirements и стадий сборки может уменьшить образ и
поверхность зависимостей; сначала сохранить идентичность runtime-набора и CI.

Приоритет: E2E/React effects/нагрузка →
внешний data host и проверенный план отказа. Полная смена Django/Next, Kubernetes
или дробление на микросервисы сейчас не обоснованы измеренной потребностью.
