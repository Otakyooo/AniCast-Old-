# Frontend Design

Создание и изменение интерфейсов AniCast на Next.js/React/CSS Modules.

## Контекст

Перед работой прочитать:

- `docs/FRONTEND_DESIGN_RULES.md`;
- `docs/BRAND_UI_TECH_SPEC.md`;
- ближайший аналог route, компонента, CSS module и API-flow.

## Правила

1. Сохранить App Router, Server Components по умолчанию, CSS Modules, Phosphor
   Icons, семантические CSS variables и существующую i18n-систему.
2. Не добавлять Tailwind, shadcn/ui, новую палитру, семейство иконок или UI-пакет
   без отдельного решения пользователя.
3. Зафиксировать основную задачу пользователя и применимые loading, empty,
   unavailable, pending, success, error, disabled и retry состояния.
4. Показывать success только после подтверждения backend; при ошибке сохранять
   полезный ввод и давать понятное восстановление.
5. Использовать native semantics, keyboard navigation, `focus-visible`, логичный
   DOM order и доступные имена.
6. Проверить узкий mobile и широкий desktop, длинный текст и обе локали, если flow
   локализован.
7. Не расширять задачу массовой очисткой соседнего legacy UI.

## Завершение

Выполнить проверки из `docs/FRONTEND_DESIGN_RULES.md`. В итогах перечислить
непроверенные browser, keyboard или screen-reader сценарии.
