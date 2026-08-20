# Edge Case Analysis

Системный проход пустых, граничных, повторных и ошибочных сценариев.

## Чеклист

- Пустой input, empty list, zero, null и максимальный размер.
- Неизвестный ID, удалённая запись, expired session и недостаточные permissions.
- Повторный request, double click, retry, out-of-order response и concurrent update.
- Timeout, partial failure, недоступные Redis/DB/provider и malformed response.
- Последняя/вне диапазона страница, refresh и direct URL.

## Процесс

1. Выбрать границы из контракта и state machine.
2. Для каждого сценария описать expected status, state, user message и recovery.
3. Добавить минимальные детерминированные regression tests.
