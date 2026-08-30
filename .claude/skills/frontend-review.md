# Frontend Review

Ревью пользовательского интерфейса AniCast перед merge или release.

## Контекст

Прочитать `docs/FRONTEND_DESIGN_RULES.md` и
`docs/BRAND_UI_TECH_SPEC.md`. Проверять наблюдаемый flow, а не только изменённые
строки JSX/CSS.

## Проверки

1. Пройти основную задачу пользователя и один отказ: empty, unavailable,
   validation или backend error.
2. Проверить component boundaries, Server/Client Components, routing, типы API,
   stale responses и быстрые повторные действия.
3. Проверить default, hover, `focus-visible`, pending, disabled, success, error и
   retry состояния затронутых контролов.
4. Убедиться, что UI не сообщает success до backend, не теряет полезный ввод и не
   скрывает частичный результат как полный.
5. Проверить native semantics, доступные имена, keyboard-only flow, focus order,
   contrast и объявления динамических статусов.
6. Проверить узкий mobile и широкий desktop, длинные названия и обе локали для
   локализованного flow.
7. Сопоставить цвета, иконки, spacing и hierarchy с проектными токенами и
   существующими общими компонентами.
8. Запустить `npm run lint`, `npm run typecheck`, `npm test` и `npm run build` из
   `frontend/`.

## Приоритет замечаний

- Blocking: невозможно завершить главный flow, теряются данные, результат показан
  неверно или flow недоступен.
- Significant: нарушены recovery, responsive layout, hierarchy, consistency или
  зафиксированное проектное правило.
- Polish: улучшение без материального влияния на выполнение задачи.

Не считать browser, keyboard или screen-reader gate пройденным, если он фактически
не выполнялся. Не превращать ревью в несвязанный массовый рефакторинг.
