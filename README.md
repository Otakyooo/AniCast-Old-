# AniCast

Русскоязычный аниме-сервис: каталог, просмотр через разрешённые провайдеры,
персонажи и авторы, расписание, личная библиотека, история, коллекции и
уведомления.

## Архитектура

- `backend/` — Django 5.2, DRF, PostgreSQL, Redis и Celery;
- `frontend/` — Next.js 15 и React 19;
- `infra/mainserver/` — backend, PostgreSQL, Redis и фоновые задачи;
- `infra/vps/` — публичный frontend и Caddy;
- `infra/monitoring/` — Prometheus, Alertmanager и blackbox-проверки;
- `scripts/` — проверка, бэкап, деплой и откат.

Production secrets хранятся только во внешних `.env`; в git их быть не должно.

## Документация

- [Статус реализации](docs/IMPLEMENTATION_STATUS.md) — что реально работает в production;
- [Эксплуатация](docs/OPERATIONS.md) — бэкапы, импорт, Kodik, деплой и rollback;
- [Бренд и цветовая система](docs/BRAND_UI_TECH_SPEC.md) — production-ассеты, токены и правила применения;
- `docs/*v2.0.docx` — продуктовая концепция и архитектурная спецификация.

## Локальная проверка

```bash
cd backend && python3 -m pytest
cd frontend && npm ci && npm run lint && npm run typecheck && npm test && npm run build

docker compose -f infra/mainserver/compose.yml config
# Для VPS:
docker compose -f infra/vps/compose.yml config
```

Полная проверка одной командой: `sh scripts/validate.sh`.

## Kodik и расписание

Команда работает в dry-run по умолчанию. Один тайтл или вся текущая библиотека:

```bash
python manage.py sync_kodik 21-one-piece
python manage.py sync_kodik --all --apply
```

Первичная активация воспроизведения требует явной ссылки на основание доступа:

```bash
python manage.py sync_kodik --all --apply --activate \
  --rights-reference="Kodik account entitlement for anicast.online"
```

После активации Celery Beat каждый час обновляет очередную ограниченную часть
библиотеки: источники, новые серии, точную дату следующего эпизода и авторов.
Подробности и процедура production-запуска — в `docs/OPERATIONS.md`.
