# Dependency Impact Analysis

Поиск затронутых зависимостей, consumers и публичных контрактов до изменения.

## Процесс

1. Найти imports, вызовы, маршруты, schema/types и конфигурационные ссылки.
2. Классифицировать зависимости как internal, public, runtime или deployment.
3. Проверить breaking changes, version constraints и порядок rollout.
4. Для каждого consumer определить нужный fix, compatibility shim или тест.
5. Проверить отсутствие orphaned code после изменения.

## Отчёт

Указывать dependency, точку использования, риск, нужное действие и команду проверки.
