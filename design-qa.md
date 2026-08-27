# Design QA — навигация просмотра

- Source visual truth: пользовательский production-скриншот AniCast с растянутым плеером (desktop, 1210 × 702 px) и указание сохранить 16:9, прокручивая только правую панель.
- Implementation screenshot: недоступен — в текущей сессии нет выбранного пользователем browser surface и browser-capture инструмента.
- Intended viewport: desktop 1180 px content width; дополнительно предусмотрен breakpoint до 640 px.
- Density normalization: не выполнялась, потому что implementation screenshot отсутствует.
- State: выбранная озвучка, активная серия, доли выбора зрителей, плеер до запуска.

**Full-view comparison evidence**

Заблокировано: исходный референс виден в сообщении, но браузерный рендер реализации нельзя открыть и снять в этой сессии. Build/typecheck не считаются визуальным доказательством.

**Focused region comparison evidence**

Не выполнялось по той же причине. При доступном browser surface отдельно проверить верхнюю строку выбора озвучки, плотность сетки серий, активное/недоступное состояния и область плеера на desktop/mobile.

**Findings**

- [P1] Нет browser-rendered сравнения с референсом.
  - Location: `/titles/<slug>/watch`.
  - Evidence: implementation screenshot отсутствует.
  - Impact: нельзя доказать визуальную плотность, прокрутку правой панели, переносы процентов и отсутствие overflow на реальных данных Kodik.
  - Fix: открыть production/local route в выбранном пользователем браузере, снять тот же state и viewport, совместить оба изображения и повторить QA.

**Required fidelity surfaces**

- Fonts and typography: код использует существующий системный стек AniCast; визуальная проверка заблокирована.
- Spacing and layout rhythm: плеер сохраняет 16:9 на всех ширинах; правая панель равна его полной высоте и прокручивается независимо. Шапки плеера и панели имеют одинаковую минимальную высоту 48 px. Визуальная проверка заблокирована.
- Colors and visual tokens: сохранены токены AniCast (`--primary`, `--surface-*`, `--border`, `--success`); визуальная проверка заблокирована.
- Image quality and asset fidelity: новых растровых ассетов нет; содержимое видео остаётся у провайдера; визуальная проверка заблокирована.
- Copy and content: RU/EN ключи покрыты unit-тестом; визуальные переносы заблокированы.

**Implementation Checklist**

- Снять desktop state с 20–30 сериями и несколькими озвучками.
- Проверить смену озвучки, сортировку и проценты, прокрутку правой панели, серии, диапазон 1–100/101–200 и запуск iframe.
- Снять mobile state до 640 px и проверить overflow.
- Проверить console errors и повторить side-by-side comparison.

**Comparison history**

- Итерация 1: код, типы, lint, unit и production build прошли; блоки «Доступно серий» и «Все источники и диагностика» удалены, добавлена статистика выбора.
- Итерация 2: по production-скриншоту удалено принудительное растягивание до 680 px, восстановлено 16:9, выровнены шапки и добавлен видимый scrollbar озвучек. Browser-rendered сравнение недоступно.

final result: blocked
