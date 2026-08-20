# Observability First

Проектирование диагностики отказов одновременно с функциональностью.

## Чеклист

- Есть structured logs с correlation/request ID, без secrets и лишних personal data.
- Метрики показывают rate, errors, latency и saturation по критическому пути.
- Ошибки имеют actionable context и не скрываются широким catch.
- Health/readiness проверяют реальные зависимости, но не создают опасную нагрузку.
- Для фоновой задачи видны retries, age, failure и dead-letter outcome.

## Процесс

1. Описать ожидаемое успешное и отказное поведение.
2. Выбрать сигналы, по которым отличить гипотезы отказа.
3. Добавить instrumentation вместе с кодом.
4. Проверить privacy, cardinality, alert threshold и runbook.
