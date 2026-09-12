# Архитектура Anicast

Текущая система — модульный Django/DRF backend, PostgreSQL и Celery на MainServer;
Next.js/Caddy на публичном VPS; приватная связь по AWG. Отдельные Redis владеют
broker/results, control и disposable cache. Monitoring не подключается к data network.

| Решение | Действующий контракт |
| --- | --- |
| [001: устойчивость](001-stability-first.md) | Сохранить Django/Next, изолировать задачи и ограничить ресурсы; первый этап реализован |
| [002: cache](002-redis-isolation.md) | Disposable cache вынесен отдельно; прежнее совместное размещение control/broker заменено ADR 005 |
| [003: firewall](003-vps-firewall.md) | Только owned nft table, сохранение Docker/AWG, закрытые служебные порты |
| [004: registry/recovery](004-registry-and-recovery.md) | CI builds, immutable digests/env, независимая репетиция восстановления |
| [005: control/offline](005-control-and-offline-recovery.md) | Третий Redis, авторитетное control state, offline credentials и RPO/RTO |
| [006: Next 16](006-next16.md) | Node proxy с nonce, Turbopack в CI, прежние runtime-лимиты и image rollback |
| [007: последовательный rollout](007-staged-rollout.md) | API readiness до обновления workers; общий порядок deploy/rollback, bulk grace 1900s |
| [008: поколения откатов](008-rollback-generations.md) | Три поколения манифестов и gate необратимых миграций; дополняет 004/007 |

ADR сохраняет контекст решения на дату принятия. При изменении границы сервисов,
владельца данных или контракта релиза добавить следующее решение и отметить,
какую часть прежнего оно заменяет. За текущими процедурами обращаться к
[эксплуатации](../OPERATIONS.md), за незакрытыми рисками — к
[технической оценке](../TECHNICAL_ASSESSMENT.md).
