# Webapp Testing

Проверка web-приложения через component, API и browser-level сценарии.

## Процесс

1. Зафиксировать пользовательский flow и ожидаемые URL, requests, responses и UI states.
2. Проверить component behavior через React Testing Library, если логика локальная.
3. Проверить API boundary с mock fetch или Django test client, не смешивая контракт с implementation details.
4. Для критических flows выполнить Playwright/browser-тест: render → interaction → result.
5. Проверить refresh, back/forward, direct URL, mobile viewport, slow network и server error.

## Чеклист

- Есть happy path, validation, unauthorized и empty/error сценарии.
- Тесты детерминированы и не используют необязательный `sleep`.
- Проверяются keyboard/focus и доступные имена элементов.
- После изменений проходят lint, typecheck и production build.
