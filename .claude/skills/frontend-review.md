# Frontend Review

Ревью Next.js/React/TypeScript UI перед merge.

## Проверки

1. Проверить component boundaries, server/client usage и routing.
2. Проверить loading, error, empty, success и повторное действие для каждого async flow.
3. Проверить типы props/API, обработку stale data и race conditions.
4. Проверить accessibility: semantic HTML, keyboard navigation, labels, focus и contrast.
5. Проверить responsive layout для desktop и mobile.
6. Запустить `npm run lint`, `npm run typecheck` и `npm run build`.

## Антипаттерны

- Business logic в JSX без выделенного service/API слоя.
- `any`, скрытые type assertions и состояние, недоступное клавиатурой.
- UI, который показывает success до подтверждения backend.
