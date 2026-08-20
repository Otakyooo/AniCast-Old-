# Cross-Module Reasoning

Оценка изменения по всей цепочке frontend → API → service → DB → infrastructure.

## Процесс

1. Начать с точки входа и проследить данные до persistence и обратно.
2. Найти consumers: frontend calls, serializers, tasks, admin, scripts и monitoring.
3. Проверить согласованность ошибок, auth, типов и retry semantics между слоями.
4. Проверить миграции, deployment order и обратную совместимость.
5. Добавить интеграционные проверки на границах, а не только unit-тесты.

## Правило

Локально зелёный тест не закрывает cross-module impact, пока не проверены соседние consumers.
