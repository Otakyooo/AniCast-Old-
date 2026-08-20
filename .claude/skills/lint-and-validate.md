# Lint and Validate

Прогон линтеров, typecheck, тестов — быстрая проверка целостности кодовой базы.

## Backend

```bash
cd backend
ruff check .
mypy --strict .
python -m pytest -x -q
```

## Frontend

```bash
cd frontend
npm ci
npm run lint
npm run typecheck
npm run build
```

## Infrastructure

```bash
docker compose -f infra/mainserver/compose.yml config
docker compose -f infra/vps/compose.yml config
```

## Правила

- Запускать перед каждым commit/merge
- Любая ошибка = блокировка, не «предупреждение»
- Если линтер даёт false positive — зафиксировать исключение в конфиге, а не игнорировать
- Порядок: lint → typecheck → tests → build (от дешёвого к дорогому)