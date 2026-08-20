# AniCast — статус MVP discovery slice

Дата: 20 августа 2026

## Готовый сквозной срез

Гостевой путь «найти тайтл → открыть карточку → понять метаданные и франшизу → увидеть эпизоды и честный статус источника» реализован локально:

- read-only API `/api/v1/titles/` с поиском `q`, пагинацией и фильтрами `type`, `status`, `genre`;
- детальная выдача по slug с жанрами, франшизой, эпизодами и availability states источников;
- deterministic demo seed через `python manage.py seed_catalog`;
- frontend `/catalog` и `/titles/<slug>` с responsive layout, loading/error/empty/not-found states;
- unavailable, geo-blocked, expired и provider-error источники показываются как статусы, без обманчивого playback/embed;
- навигация будущих разделов явно отключена, без inert `href="#"`.

## Ограничения проверки

Frontend-проверки требуют установки зависимостей из `frontend/package-lock.json`. Backend-проверки требуют Python packages из `backend/requirements.txt`; если окружение не содержит pip/Django, команды остаются заблокированными и не считаются успешно пройденными.

## Что реализовано

Дата: 20 августа 2026

## Изученные требования

Перед началом реализации изучены три документа в `docs/`:

- функциональная концепция и приоритеты v2.0;
- техническая архитектура и план развертывания v2.0;
- дизайн-концепция и UX-направление v0.1.

Документы в `docs/` сохранены без изменений.

## Что реализовано

### Backend

- Django 5.2 + Django REST Framework;
- базовый модульный монолит `config`/`common`;
- endpoints `/health/live` и `/health/ready`;
- PostgreSQL как production database и SQLite-режим для локальных тестов;
- Django Sessions, HttpOnly/Secure cookies и CSRF baseline;
- Celery configuration;
- Dockerfile, pytest, Ruff и mypy configuration.

### Frontend

- Next.js 15 + React + TypeScript;
- standalone production build;
- базовая главная страница AniCast;
- тёмная UI-система с фиолетовым акцентом;
- desktop-sidebar и mobile-adaptive layout;
- базовая поисковая строка и персональный вход;
- ESLint и TypeScript configuration.

### Infrastructure

- MainServer Compose: PostgreSQL, Redis, Django, Celery worker и Celery Beat;
- внутренние Docker networks и healthchecks;
- backend bind на `10.78.0.2:8000`;
- VPS Compose с frontend на `127.0.0.1:3000`;
- Caddy routing: `/api/*` через AmneziaWG на backend, остальной трафик на Next.js;
- env-примеры без production secrets;
- корневой `.gitignore` и README.

## Проверки

На этапе подготовки были успешно выполнены:

- backend tests: `2 passed`;
- Ruff: `All checks passed`;
- mypy: `Success: no issues found`;
- Django system check: без ошибок;
- frontend lint: без warnings и errors;
- frontend typecheck: успешно;
- frontend production build: успешно;
- MainServer Docker Compose config: успешно;
- VPS Docker Compose config: успешно.

Backend-тесты выполнялись с локальным SQLite. PostgreSQL hostname `postgres` доступен внутри Docker Compose network.

## Не реализовано на этом этапе

Следующие части оставлены для следующих итераций:

- регистрация, вход и пользовательские сессии на уровне продукта;
- история, прогресс, списки и расписание;
- provider adapter, playback states и rights registry;
- контентная админка, аудит и аналитика;
- персонажи, личные заметки, community и moderation;
- уведомления, рекомендации, Premium и внешние каналы;
- production deployment, backup/restore и monitoring automation.

## Известное расхождение требований

Дизайн-концепция фиксирует персонажей и личные заметки как часть Wiki-направления v0.1, а функциональная концепция относит соответствующую функциональность к последующим этапам. В текущей итерации это учтено как будущее расширение, без включения в P0-функциональность.

## Git

Перенос выполнен в репозиторий `/home/lama_admin/anicast`. Существующий Git history сохранён. Commit, push и merge не выполнялись.
