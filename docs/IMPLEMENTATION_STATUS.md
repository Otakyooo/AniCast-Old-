# Anicast: текущее состояние

Проверено 09.09.2026. Это текущая сводка; последовательность релизов и прежние
планы находятся в [архиве](archive/README.md).

## Что работает

- Next.js 15 / React 19 / TypeScript: каталог, плеер разрешённых источников,
  библиотека, история, коллекции, публичные opt-in профили, поиск, уведомления.
- Django 5.2 / DRF / PostgreSQL 17 на MainServer; публичный Next/Caddy на VPS,
  связь через AWG. Backend — модульный монолит.
- Три Redis: broker/results, обязательная координация и необязательный cache.
  Два Celery workers с concurrency 1; отдельные очереди уведомлений и bulk.
- Светлая, тёмная и системная темы, Manrope, SVG бренд и metadata. HTML получает
  уникальный nonce CSP и private/no-store; image cache переживает релиз.
- CI проверяет backend/frontend/infrastructure и публикует GHCR images по digest.
  Есть immutable release env, health gates, image rollback, firewall и мониторинг.
- Внешние зашифрованные DB/media backups и recovery kits. Собственный Google
  OAuth активен; refresh/read/write и SHA-256 новой копии проверены вне MainServer.
  Последние kits: 20260908T234633Z, все 21/11 файлов проверены.
- Полная изолированная репетиция restore/login/reset/notification sink/player
  и private proxy switch/rollback прошла за 142.16s без скачивания файлов/образов.

## Ресурсы и ограничения

MainServer: 1 CPU, около 2.5 GiB RAM. Владелец позже увеличит только RAM до 4 ГБ;
сейчас лимиты и concurrency сохранены. VPS: 1 CPU, около 1 GiB RAM.
В суточной истории MainServer были активный swap и минимум 459 MiB доступной RAM;
последний измеренный час — минимум 1056 MiB. Это не нагрузочный предел сайта.

MainServer, домашний канал/питание и единственный VPS остаются точками отказа.
Нет подтверждённого HA или постоянного переноса API/БД; внешний хост не предоставлен.
RPO-цели 6h DB / 24h media зависят от успеха offsite, RTO-цель 2h — от наличия
хоста и ключей. Полный mobile/screen-reader E2E и нагрузочная ёмкость не доказаны.

## Ближайшие приоритеты

1. Закрыть выявленные npm advisories и добавить frontend dependency audit в CI.
2. Запланировать переход с Next 15 до окончания его окна поддержки.
3. Проверить критические браузерные сценарии в воспроизводимом E2E и нагрузку.
4. Перенести data tier на предоставленный внешний хост; RAM дома этого не заменяет.

[Оценка стека и доказательства](TECHNICAL_ASSESSMENT.md),
[эксплуатация](OPERATIONS.md), [архитектура](architecture/README.md).
