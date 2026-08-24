# AniCast

Технический фундамент русскоязычного аниме-сервиса по спецификациям в `docs/`.

## Локальная проверка

```bash
cd backend && python3 -m pytest
cd frontend && npm ci && npm run lint && npm run typecheck && npm test && npm run build

docker compose -f infra/mainserver/compose.yml config
# Для VPS:
docker compose -f infra/vps/compose.yml config
```

Production secrets не хранятся в репозитории: используйте `/etc/anicast/.env`.
