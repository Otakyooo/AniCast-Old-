# Release Readiness

Финальная комплексная проверка перед merge и deploy.

## Чеклист

1. Требования, scope и acceptance criteria проверены.
2. Backend: `ruff check .`, `mypy --strict .`, `python -m pytest -x -q`.
3. Frontend: `npm run lint`, `npm run typecheck`, `npm run build`.
4. Compose: оба файла проходят `docker compose ... config`.
5. Миграции обратимы, данные защищены, rollback и deploy order описаны.
6. Auth, permissions, secrets, CSRF, cookies и input validation проверены.
7. Ошибки наблюдаемы без утечки sensitive data; healthchecks и alerts достаточны.
8. Документация, decision log и review handoff обновлены.

## Правило

Любой красный тест, неизвестный breaking change или отсутствие rollback для destructive operation блокирует release.
