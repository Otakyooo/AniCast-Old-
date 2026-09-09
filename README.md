# Anicast

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

[Индекс документации](docs/README.md) · [Оценка стека](docs/TECHNICAL_ASSESSMENT.md) · [Архитектура](docs/architecture/README.md)


- [Статус реализации](docs/IMPLEMENTATION_STATUS.md) — что реально работает в production;
- [Эксплуатация](docs/OPERATIONS.md) — бэкапы, импорт, Kodik, деплой и rollback;
- [Бренд и цветовая система](docs/BRAND_UI_TECH_SPEC.md) — production-ассеты, токены и правила применения;
- [Правила проектирования интерфейса](docs/FRONTEND_DESIGN_RULES.md) — UX, состояния, адаптивность, доступность и design QA;
- [SEO-процесс](docs/SEO_OPERATIONS.md) — матрица индексирования, release gate, KPI и рабочий цикл;
- [Брендбук v0.1](docs/Anicast-Brand-Guide-v01.pdf) — источник новой палитры и тем.

## Локальная проверка

Команды для backend, frontend и инфраструктуры находятся в
[Deployment / Validation](docs/operations/DEPLOYMENT.md#validation).
`sh scripts/validate.sh` проверяет инфраструктуру и release scripts;
полные тесты приложений и сборки дополнительно выполняет CI.

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
