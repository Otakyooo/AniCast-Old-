# Performance Reasoning

Оценка запросов, объёмов данных, latency и стоимости выполнения.

## Процесс

1. Описать workload: users, request rate, dataset size, latency target и допустимую freshness.
2. Найти N+1, full scans, лишние сериализации, большие payloads и повторные network calls.
3. Проверить индексы, pagination, select/prefetch, cache invalidation и queue backpressure.
4. Измерить до и после на representative data; не заменять benchmark догадкой.
5. Проверить worst-case, cold cache, concurrent requests и деградацию зависимости.

## Правила

- Оптимизация не должна ломать correctness, permissions или observability.
- Cache без стратегии invalidation и bounds считается дополнительным состоянием и риском.
