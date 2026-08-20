# Data Flow Analysis

Прослеживание данных от UI до API, service, DB и обратно.

## Процесс

1. Отметить источник, формат, владельца и trust boundary каждого значения.
2. Проследить validation, normalization, transformation и storage.
3. Проверить, не теряются ли типы, precision, encoding или ошибки.
4. Проверить secrets и personal data в логах, ответах и telemetry.
5. Сопоставить response с потребителем и проверить обратный путь ошибок.

## Чеклист

- Input валидируется на границе.
- SQL выполняется через безопасный ORM/API.
- Output экранируется в нужном контексте.
- Ошибка не раскрывает внутренние данные.
