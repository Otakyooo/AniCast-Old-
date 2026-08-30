# AniCast — бренд и цветовая система

Версия: 1.0
Дата: 27 августа 2026

## Назначение

Документ фиксирует production-источники бренда, семантические цветовые токены и правила их применения во frontend AniCast. Каноническая реализация токенов находится в `frontend/app/globals.css`; локальные CSS-модули должны использовать переменные, а не копировать hex-значения.

Правила компоновки, компонентов, состояний, доступности и design QA находятся в
`docs/FRONTEND_DESIGN_RULES.md`. При визуальном изменении применяются оба
документа.

## Брендовые ассеты

| Ассет | Путь | Назначение |
| --- | --- | --- |
| Компактный знак | `frontend/public/brand-mark.png` | Шапка, авторизация и fallback отсутствующего портрета персонажа |
| Favicon | `frontend/app/icon.png` | Иконка вкладки и metadata route Next.js |
| Apple touch icon | `frontend/app/apple-icon.png` | Закладка на iOS/iPadOS |
| Social preview | `frontend/public/og.png` | Open Graph и Twitter preview, 1200×630 |
| Иллюстрация 404 | `frontend/public/not-found-brand.webp` | Брендовая страница неправильного URL |

Исходники пользователя хранятся в `docs/` и не используются приложением напрямую. Компактный знак подготовлен из `docs/99d33be3-e102-4ed1-943a-31b40af01fd5.png`: удалён только тёмный фон, сохранены маскот, красное солнце и исходная форма знака. В шапке знак объединяется с HTML-wordmark `AniCast`, чтобы текст оставался резким, доступным и адаптивным.

## Цветовые токены

| Семантика | CSS token | Значение |
| --- | --- | --- |
| Основной фон | `--background` | `#0B131C` |
| Повышенная поверхность / header / sidebar | `--surface-elevated` | `#141E2A` |
| Карточки | `--surface-card` | `#1B2330` |
| Поверхность плеера и медиа | `--surface-media` | `#080B12` |
| Фон отсутствующего постера | `--surface-poster` | `#24303E` |
| Дорожка прогресса | `--surface-progress` | `#232A37` |
| Элемент управления просмотром | `--surface-control` | `#202632` |
| Hover управления просмотром | `--surface-control-hover` | `#292F3D` |
| Границы | `--border` | `#2A3442` |
| Основной текст | `--text` | `#F3EDE2` |
| Вторичный текст | `--muted` | `#A8B1BD` |
| Приглушённый текст | `--muted-2` | `#8793A1` |
| Акцент | `--primary` | `#E04F3E` |
| Hover акцента | `--primary-hover` | `#FF6A4D` |
| Акцентный текст | `--accent-text` | `#FF6A4D` |
| Текст на акценте | `--on-primary` | `#0B131C` |
| Success | `--success` | `#3BA97C` |
| Success-текст малого размера | `--success-text` | `#48B889` |
| Warning | `--warning` | `#E0A23A` |
| Error | `--danger` | `#E05A5A` |
| Focus ring | `--focus-ring` | `#FF8A73` |

Прозрачные состояния и составные роли также определяются в `globals.css`:

- `--primary-soft`, `--primary-border`, `--primary-ring`;
- `--success-soft`, `--success-border`;
- `--warning-soft`, `--warning-border`;
- `--favorite`, `--favorite-border`, `--favorite-surface`;
- `--border-media`, `--border-emphasis`, `--border-muted`;
- `--poster-gradient`, `--shadow-media`;
- `--profile-banner`, `--profile-banner-overlay`, `--profile-avatar-gradient`,
  `--profile-activity-gradient`, `--profile-genre-gradient`, `--shadow-profile-avatar`.
- `--public-profile-banner`, `--public-profile-avatar-gradient`,
  `--background-translucent`.
- `--surface-card-opaque`, `--danger-soft`, `--danger-border`;
- `--auth-background`, `--not-found-background`, `--brand-text-gradient`,
  `--media-edge-gradient`, `--shadow-overlay`, `--shadow-illustration`.
- `--primary-surface-gradient`, `--avatar-control-gradient`,
  `--surface-gradient`, `--collection-initial-gradient`.
- `--home-hero-overlay`, `--home-hero-overlay-mobile` — читаемые desktop/mobile
  overlays для декоративного artwork в hero главной.

Совместимые алиасы существующей системы:

- `--surface-1` → `--surface-card`;
- `--surface-2` → `--surface-elevated`.

Они сохраняют обратную совместимость компонентов и позволяют постепенно переходить на семантические имена.

## Правила применения

- Основной фон страницы всегда использует `--background`.
- Шапка, sidebar, dropdown и вложенные управляющие поверхности используют `--surface-elevated`.
- Карточки, панели контента и empty states используют `--surface-card`.
- `--muted-2` применяется только к вспомогательным подписям; значение сохраняет контраст не ниже 5.05:1 на самой светлой стандартной поверхности. Для основного текста и важных действий нужен `--text` или `--muted`.
- Кнопки с фоном `--primary` используют `--on-primary`, а не белый текст: контраст `#0B131C` на `#E04F3E` составляет примерно 4.77:1.
- Мелкий акцентный текст на стандартных тёмных поверхностях использует `--accent-text`, а не `--primary`; минимальный контраст составляет 5.58:1.
- Ошибки, предупреждения и success-состояния используют только соответствующие семантические токены.
- Focus-visible нельзя заменять hover-состоянием или убирать без равноценной альтернативы.
- Фиолетовые legacy-градиенты и rgba-значения не возвращаются в новые компоненты.

## Интеграция

- Общий компонент логотипа: `frontend/components/brand-lockup.tsx`.
- Японские локализованные названия используют self-hosted variable font Noto Sans JP из [`@fontsource-variable/noto-sans-jp`](https://fontsource.org/fonts/noto-sans-jp) версии 5.3.0; пакет распространяется по OFL-1.1 и загружается по unicode-range только для реально встреченных глифов.
- Header и страницы входа/регистрации используют один и тот же компонент.
- Next.js автоматически публикует `app/icon.png` и `app/apple-icon.png` как metadata assets.
- `themeColor` браузера синхронизирован с `#0B131C` через `viewport` в корневом layout.
- Open Graph metadata продолжает ссылаться на `/og.png` с размером 1200×630.

## Проверка изменений

Перед релизом обязательны:

1. `npm run typecheck`;
2. `npm run lint`;
3. `npm test`;
4. `npm run build`;
5. проверка favicon, header, login/register и 404 на desktop и mobile;
6. проверка focus-visible и контраста интерактивных состояний.
