# Этап 2: Redis isolation, 08.09.2026

## Изменения

Необязательные счётчики перенесены в отдельный Redis на MainServer. Docker limit
96 MiB, Redis maxmemory 64 MiB, allkeys-lru, без persistence и публичных портов.
На VPS новый сервис не добавляется. Старый Redis сохраняет broker, task results,
throttles, locks, cursors; ключи и очереди не очищаются. Сессии остаются в PostgreSQL.

Ошибки telemetry cache не делают API недоступным: сетевые операции ограничены,
после ошибки действует пауза 5 секунд на процесс. Обязательный control cache
остаётся в readiness. Новые Redis metrics и два Prometheus alerts показывают
отказ роли и заполнение control выше 80%.

Архитектура и ограничения: [ADR 002](../../architecture/002-redis-isolation.md).

## Проверки

- 337 pytest-тестов backend: успешно, 4 существующих предупреждения.
- Ruff и mypy: успешно (152 source files); после исправления аннотации настроек
  повторно пройдены 5 целевых тестов, Django check и отсутствие новых миграций.
- В отдельных Docker Redis без production volumes/сети: заполнение cache с
  фактическим eviction; доставка сообщения, сохранность throttle и lock.
- После остановки тестового cache: публикация/получение нового сообщения и
  сохранность coordination state. Оба сценария прошли; контейнеры удалены.
- Unit-тесты API и readiness при отказе необязательного cache, fail-closed
  readiness при отказе control, восстановление telemetry после паузы.
- Infrastructure validation: Compose, shell, 21 Prometheus rule, Alertmanager,
  deploy/rollback regression tests — успешно.
- Дамп БД перед выкладкой создан, `pg_restore --list` прошёл. Restore на другом
  сервере и нагрузочный тест production не выполнялись.

## Выкладка и откат

Предрелизный снимок: `/home/lama_admin/anicast/backups/predeploy-20260908-redis/`.
Содержит исходные Compose/rules, пользовательский diff, image ID, DB dump,
приватные env snapshots. Пароли не включены в git или этот отчёт.

`rollback-runtime.env` сохраняет старый CACHE_URL для старого backend и пароль
нового cache-сервиса. `release-runtime.env` содержит оба новых URL. Манифесты
current/previous ссылаются на соответствующий снимок: обычный image rollback
возвращает прежние подключения, оставляя cache-сервис доступным. Не редактировать
эти снимки при следующем релизе. Полный откат топологии дополнительно требует
сохранённых Compose/rules. PostgreSQL не восстанавливать ради отката образа.

Выкладка завершена: deploy.sh exit 0, все сервисы healthy, Django production
check без issues. Фоновые workers штатно остановились до пересоздания Redis/PostgreSQL;
после релиза оба запущены и healthy. Публичные home/API: 200, metrics: 404.
Backend image: `sha256:f442e936b303e206b024e481f5c19c7ed6642683480bfb00c5aa6000a7822b1c`.

Финальный снимок: redis-cache container 3.50 MiB / 96 MiB, control 9.04 MiB / 256 MiB,
backend 161.8 MiB / 512 MiB. MainServer available 846 MiB. Это разовый замер,
не нагрузочный тест. VPS не пересобирался и не получал новых сервисов.

При проверке Prometheus обнаружен отдельный эксплуатационный дефект: токены были
600 и недоступны пользователю nobody в контейнерах. Исправлено на 640 с группой
65534, без доступа для остальных пользователей; env-файлы остались 600.
Правила Prometheus перечитаны, фактические samples обеих Redis roles получены
со значением 1. Добавлен verify-monitoring.sh против повторения этого дефекта.
Реальная отправка Telegram в качестве теста не выполнялась.

## Оставшиеся риски

Control/queues/results всё ещё разделяют лимит одного Redis. MainServer, питание
и туннель остаются точками отказа. Общая внутренняя Docker-сеть не является полной
изоляцией доверия. Счётчики могут обнуляться при eviction/restart; история
Prometheus сохраняется. Требуются отдельная репетиция восстановления и дальнейшая
работа с firewall/CI. Предыдущие удаления трёх изображений пользователя сохраняются
вне этого коммита.
