# 09.09.2026: Next 16, две темы и обновлённая админка

Основной исходный commit: `34b468b66d9bd968f26293e049f67cb2e4e7925a`.
[Publish CI 34343220545](https://github.com/Otakyooo/AniCast/actions/runs/34343220545)
прошёл полностью, оба образа опубликованы и развёрнуты по digest.

| Компонент | Основной релиз |
| --- | --- |
| Backend | `ghcr.io/otakyooo/anicast-backend@sha256:22b5a1aa8fcb3401286850c53673c9f5b0ca81fc7f5cba60bb0cd5111b97487b` |
| Frontend | `ghcr.io/otakyooo/anicast-frontend@sha256:a28a5bc92e3d3614c134dc71e3919979a872117323534bfeaf10b24484545070` |

При окончательной проверке найдено переполнение страницы тайтла: auto tracks
вложенных grid растягивались до ширины ленты похожих тайтлов (около 1980 px).
Commit `cb586def770d3e116e8ef76f2fe244dece47018b` ограничивает четыре сетки
через `minmax(0, 1fr)`. [Publish CI 34345568637](https://github.com/Otakyooo/AniCast/actions/runs/34345568637)
полностью прошёл; только frontend повторно развёрнут по окончательному digest
`ghcr.io/otakyooo/anicast-frontend@sha256:86beac883ad0a5d741ebac9c7fc84e867ee58a255fa60a47caa7724e37cd5dea`.
Backend остался на основном digest; дополнительных изменений БД/runtime нет.

Проверка окончательного production CSS без подмены: обе темы, ширины
1280/820/390 px, scrollWidth равен viewport во всех шести сочетаниях;
ширина блока плеера 1232/772/360 px. До правки переполнение воспроизведено на
всех трёх ширинах. Финальный smoke: home 200 / 0.757s, API 200 / 0.454s,
internal metrics 404. Это проверка layout, не полного сценария воспроизведения.

## Изменения

- Next 16.3.4 / React 19.2.8, Turbopack, native ESLint flat config; middleware
  заменён на Node proxy. Nonce CSP, private/no-store и image cache сохранены.
- Только светлая и тёмная темы, default dark; legacy `system` также становится
  dark. Общий выбор для сайта и админки, storage events между вкладками;
  недоступность storage не мешает переключению в текущей вкладке.
- У SVG логотипа удалена белая CSS-подложка, рисунок маскота сохранён.
- Django admin получил внешние брендовые static CSS/JS, адаптивные карточки,
  читаемые формы и двухпозиционный выбор темы. Прежний inline CSS блокировался
  production CSP; защиту ради оформления не ослабляли. Модели/права/действия сохранены.
- Небольшие совместимые React исправления: JSX страницы тайтла вынесен из try/catch,
  удаление коллекции использует router navigation.
- Skills UI и текущие runbooks приведены к новым темам, proxy и browser CI;
  [ADR 006](../../architecture/006-next16.md) фиксирует техническое решение.

## Проверки

CI: lint/typecheck/build, 73 frontend unit tests, 9 Chromium E2E на 1440×900,
820×1180 и 390×844; backend и infrastructure gates, native sharp/libvips в Alpine.
Проверки npm audit прошли без известных уязвимостей. Сборка сохранила heap
768 MiB; frontend runtime heap 320 MiB / container 512 MiB, concurrency не увеличены.

Локально дополнительно прошли 53 целевых backend теста. Админка проверена на
трёх шаблонах (dashboard/list/add form), в двух темах и на трёх ширинах — 18
сочетаний под CSP, без переполнения страницы. Эти проверки использовали
изолированную preview DB; production-формы не отправлялись.

В production проверены главная, каталог и страница тайтла, прозрачность логотипа,
стили админки и переключение темы сайт → админка → сайт. В каталоге 22 изображения
без broken images; консоль без ошибок. На главной ранее проверены 42 изображения.
Публичные `/` и titles API вернули 200 (0.734s / 0.366s), `/internal/metrics` — 404.
После запуска всех контейнеров MainServer и VPS health gates успешны.

Настоящий новый постер через production optimizer Next 16: WebP, 256 px,
46 520 bytes. MISS — 6445 ms, повторный HIT — 27 ms. Это один запрос,
а не нагрузочный benchmark или оценка числа зрителей.

## Ресурсы

ОС MainServer уже видит 3606.473 MiB RAM и один CPU. В окне 10:03–11:03 UTC
получены все 13 отсчётов: available RAM минимум 2055.602 MiB, CPU busy (5m)
максимум 15.837%, iowait 0.615%, swap in/out 0.156/0.226 pages/s.
VPS имеет 961.473 MiB RAM; minimum available в том же часу 486.961 MiB,
после холодного optimizer запроса — 323 MiB, занятый swap 59 MiB.
Сборки выполнялись на рабочей станции/CI; новые production-сервисы не добавлялись.

## Развёртывание и восстановление

До backend rollout создан dump `anicast-20260909T110047Z.dump`, 3 563 783 bytes.
Проверены заголовок/TOC через pg_restore и независимое скачивание из Drive:
SHA-256 `4fe2227984ccf78c25487acb367ddadda91e16fb3eddb1ab90bbbbce2ab1e0a0`.
Полного повторного restore этого dump в данном релизе не было; предыдущая
изолированная репетиция описана в [hardening](RELEASE-2026-09-09-hardening.md).

Новые age kits `20260909T111632Z`: 21 файл MainServer / 11 VPS. Все внутренние
SHA-256 проверены операторским ключом вне серверов; copies из Drive совпали
с локальными age. Current manifests внутри kits соответствуют двум digest
основного релиза. Временный plaintext rclone config удалён после проверки.
После финальной CSS-правки выпущены ещё одни kits `20260909T113324Z`: все 21/11
файлов проверены вне серверов, current manifests соответствуют основному backend
и окончательному frontend. Обе offsite age copies и предрелизный DB dump снова
независимо скачаны и сверены по SHA-256; временные plaintext файлы удалены.
Ручные backups выполнялись с `BACKUP_NOTIFY=0`, сообщений людям не отправляли.

Сохранены приватные rollback manifests, operator env и Compose снимки. Новый
релиз использует прежние immutable runtime env; PostgreSQL и три Redis не
перезапускались, миграций схемы нет. Три прежних удаления PNG в Main checkout
оставлены без изменения.

Во время Main rollout Compose пересоздал API/default worker/beat, но ожидание
старого bulk worker задержало их запуск. Новый API, затем default worker и beat
запущены отдельно во время drain. Bulk был заменён после ожидания примерно
8 минут; итоговые health gates успешны. Была пауза доступности API; нулевой
downtime и чистое завершение конкретной старой bulk задачи не подтверждены.
Нужно разделить фазы deploy и согласовать 600s grace с длительными задачами.

## Оставшиеся границы

18 `react-hooks/set-state-in-effect` предупреждений временно оставлены в 12
перечисленных старых компонентах. Остальные lint errors блокируют CI. Изменение
effects требует сценарных тестов, а не механического подавления диагностик.
Browser CI покрывает общий каркас с anonymous API fixtures; реальные вход,
плеер, полный screen-reader flow и нагрузочная ёмкость остаются отдельной работой.
Домашний data host и единственный VPS по-прежнему являются точками отказа.
