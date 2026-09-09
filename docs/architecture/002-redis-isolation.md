# ADR 002: изоляция необязательного кеша

Дата: 08.09.2026. Статус: принято.

## Причина

На MainServer Redis хранит broker (DB 0), результаты Celery (DB 1) и Django
cache (DB 2). Последний содержит не только счётчики, но и throttles, locks,
курсор обхода каталога. Включать eviction для всего инстанса нельзя.
Разные DB внутри одного Redis не изолируют его память и политику вытеснения.

Перед изменением: Redis used_memory 3.01 MiB, peak 3.45 MiB; MainServer available
629 MiB из 2582 MiB. На VPS ничего не добавляется.

## Решение

- Существующий `redis`: 256 MiB container / 200 MiB maxmemory, AOF, noeviction.
  DB 0/1 остаются Celery, DB 2 — coordination state. `CONTROL_CACHE_URL` задаёт
  Django alias `default`, сохраняя прежние ключи и их TTL без миграции.
- Новый `redis-cache`: 96 MiB container / 64 MiB maxmemory, allkeys-lru, без
  AOF/RDB, без опубликованных портов, с отдельным паролем. `CACHE_URL` задаёт
  alias `ephemeral`. Пока туда пишутся только необязательные счётчики метрик;
  будущий кеш ответов должен использовать этот alias явно.
- Старые конфигурации без `CONTROL_CACHE_URL` используют `CACHE_URL` для обоих
  alias. Это совместимость, а не изоляция: production env обновляется отдельно.
- Throttles, locks, cursors остаются на `default`. Сессии остаются в PostgreSQL.
  Переполнение/очистка disposable cache не сбрасывает ограничения или блокировки.
- Redis socket/connect timeout 0.3 s, без повторных попыток Django cache.
  Счётчики при ошибке пропускаются с паузой 5 s между попытками на процесс:
  один scrape не умножает задержку на количество метрик. Это потеря телеметрии,
  не резервное хранилище. В первые 5 s после восстановления часть метрик теряется.
- Readiness продолжает проверять обязательные database/control cache. Отказ
  `ephemeral` не останавливает API. Deploy отдельно требует healthy обоих Redis.
  На scrape экспортируются Redis up, used_memory, maxmemory, evicted_keys;
  действуют alerts отказа роли и заполнения control выше 80%.

## Ограничения

Broker, task results и coordination state всё ещё делят один Redis и предел памяти.
Данные ограничителей могут заполнить его; этот риск теперь измеряется отдельно.
Одинаковый Docker network не является полной изоляцией доверия между процессами.
Перенос счётчиков начинает новые временные ряды с нуля; Prometheus хранит историю.
У persisted locks остаются прежние ограничения TTL и владения блокировкой.
Это не high availability и не перенос API/БД на слабый VPS.

## Выкладка и откат

Сохранить Compose, приватный env, live image, release manifest и дамп БД.
Задать `CONTROL_CACHE_URL` равным прежнему `CACHE_URL`; сгенерировать отдельный
`CACHE_REDIS_PASSWORD` и направить новый `CACHE_URL` на `redis-cache` DB 0.
Очереди и DB 2 не чистить. Запустить новый Redis до новой версии приложения.

Image-only rollback недостаточен: старый backend знает только CACHE_URL.
При полном откате вернуть сохранённые env/Compose/image вместе, закончить bulk
задачи штатно, проверить оба workers и API. Остановить redis-cache можно только
после переключения всех клиентов обратно. Базу PostgreSQL для отката не менять.

## Основания

- [Redis: maxmemory и eviction](https://redis.io/docs/latest/develop/reference/eviction/).
- [Django 5.2: именованные caches](https://docs.djangoproject.com/en/5.2/topics/cache/).

Фактические проверки и выкладка: [отчёт этапа](../archive/releases/RELEASE-2026-09-08-redis.md).
