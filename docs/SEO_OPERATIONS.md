# AniCast — SEO-процесс и технический контроль

Версия: 1.2
Дата: 2 сентября 2026

## Цель

SEO для AniCast — это управляемый цикл «доступность → индексирование → качество сниппета → полезный переход», а не разовая расстановка meta-тегов. Приоритетные посадочные страницы: главная, каталог и его пагинация, расписание, тайтлы, персонажи, франшизы, сообщество, медиа и публичные коллекции.

## Матрица индексирования

| Группа URL | Политика | Причина |
| --- | --- | --- |
| `/`, `/catalog`, `/catalog?page=N`, `/schedule`, `/community`, `/media` | `index, follow`, self-canonical | Самостоятельные публичные страницы |
| `/franchises`, `/franchises?page=N`, `/franchises/<slug>` | `index, follow`, self-canonical | Франшиза — связующая сущность каталога, раздел есть в основной навигации |
| `/titles/<slug>`, `/characters/<slug>` | `index, follow`, self-canonical | Основной энциклопедический контент |
| `/collections/<owner>/<slug>` | `index, follow`, self-canonical | Публичная авторская подборка с SSR-контентом |
| `/users/<public_id>` | `index, follow`, self-canonical | Только явно включённый публичный профиль с SSR-коллекциями и рецензиями |
| Поиск, сортировка и фильтры `/catalog?...` | `noindex, follow`, canonical на `/catalog` | Не создавать индекс из комбинаций фасетов |
| Поиск франшиз `/franchises?q=...` | `noindex, follow`, canonical на `/franchises` | Результат site-search — дубль индекса, а не посадочная страница |
| Архивные недели `/schedule?week=...` | `noindex, follow`, canonical на `/schedule` | Не создавать бесконечный календарь |
| Playback-состояния `/titles/<slug>?episode=N&voice=KEY#watch` | `index, follow`, canonical на чистый URL тайтла | Query и fragment управляют встроенным плеером, но не создают отдельную посадочную страницу |
| Legacy HTML `/titles/<slug>/episodes/<number>` и `/titles/<slug>/watch` | HTTP 404 без redirect | Публичный UI-маршрут удалён; возвращать дубль или перенаправлять crawler на слабый URL не нужно |
| Degraded-рендер публичной страницы (API недоступен) | `noindex, follow` + canonical на тот же URL | Оболочка «сайт недоступен» отвечает 200 и не должна заменить настоящую страницу в индексе |
| Account, library, history, notes, settings, recommendations, управление коллекциями | `X-Robots-Tag: noindex, follow` | Личные или служебные HTML-страницы |
| `/api/`, `/staff` | `Disallow` в `robots.txt` | Служебные маршруты, не являющиеся посадочными |
| `/api/v1/media/` | `Allow` в `robots.txt` | Постеры и портреты публикуются как `og:image` и `image` в JSON-LD; закрывать их — значит скрыть от crawler'а всю графику сайта |

`robots.txt` не используется как замена `noindex`: crawler должен получить HTML или HTTP-заголовок, чтобы удалить URL из индекса. Обратное тоже верно: если URL опубликован в метаданных, он обязан быть разрешён к обходу, поэтому `Allow: /api/v1/media/` длиннее и приоритетнее общего `Disallow: /api/` (RFC 9309).

## Релизный gate

Каждый frontend-релиз проходит:

1. `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`;
2. `robots.txt` содержит production sitemap, не блокирует индексируемые страницы и не блокирует медиа, на которые ссылаются `og:image` и JSON-LD;
3. sitemap отвечает `200`, содержит только canonical URL и не содержит личных/фильтрованных/watch URL;
4. шаблоны `/`, `/catalog`, `/franchises`, `/titles/<slug>`, `/characters/<slug>` имеют уникальные title, description и canonical, и ни один title не содержит бренд дважды;
5. личная страница возвращает `X-Robots-Tag: noindex, follow`;
6. обычный missing route отвечает HTTP 404; вышедшая за диапазон пагинация не менее обязана отдавать `noindex` и canonical на базовый раздел;
7. JSON-LD валиден и совпадает с видимым контентом: `aggregateRating` публикуется только при том же пороге голосов, при котором рейтинг виден на странице (`MIN_RATING_VOTES`);
8. query-состояние плеера сохраняет canonical на чистый тайтл, а legacy UI-маршруты отвечают 404 без redirect;
9. public smoke не показывает 5xx, firing alerts отсутствуют.

Минимальный smoke после production-деплоя:

```bash
curl -fsS https://anicast.online/robots.txt
curl -fsS https://anicast.online/sitemap.xml >/dev/null
curl -fsSI https://anicast.online/account | grep -i x-robots-tag
curl -fsS https://anicast.online/titles/21-one-piece | grep -E 'canonical|application/ld\+json'
curl -fsS 'https://anicast.online/titles/21-one-piece?episode=1&voice=invalid' | grep -E 'canonical|application/ld\+json'
test "$(curl -sS -o /dev/null -w '%{http_code}' https://anicast.online/titles/21-one-piece/episodes/1)" = 404
test "$(curl -sS -o /dev/null -w '%{http_code}' https://anicast.online/does-not-exist)" = 404
```

## Рабочий цикл

### Еженедельно

- Google Search Console: Page indexing, Sitemaps, Core Web Vitals, Manual actions;
- сравнить количество отправленных и индексированных canonical URL;
- разобрать новые причины исключения, 404/5xx и страницы «Crawled — currently not indexed»;
- проверить 10 самых показательных URL через URL Inspection: главная, каталог, новая карточка, популярная карточка, персонаж и публичная коллекция;
- сопоставить crawl/5xx с Caddy и Prometheus, не анализируя пользовательские данные.

### Ежемесячно

- экспортировать из Search Console запросы и страницы за 28 дней с сравнением к предыдущему периоду;
- группировать показатели по шаблонам URL, а не по отдельным случайным страницам;
- найти страницы с высокими показами и низким CTR, проверить соответствие title/H1/description намерению запроса;
- найти страницы на позициях 8–20 и усилить именно полезный контент: описание, связи, персонажей, расписание и внутренние ссылки;
- проверить orphan URL и глубину перехода от главной/каталога.

### После изменения шаблона

- проверить 3–5 реальных URL этого шаблона в production HTML;
- провести Rich Results Test для изменённого structured data;
- запросить повторный обход только ключевых страниц, не отправлять массово неизменившиеся URL;
- оценивать эффект после повторного обхода и обработки, а не в день релиза.

## KPI

- клики, показы, CTR и средняя позиция по группам URL;
- доля валидных индексируемых canonical URL;
- причины исключения из индекса и их недельная динамика;
- sitemap fetch status и расхождение submitted/indexed;
- p75 Core Web Vitals по mobile;
- Googlebot 5xx, soft 404 и среднее время ответа;
- число страниц без уникального title/description/canonical.

Рост числа проиндексированных URL сам по себе не является целью: фильтры, личные страницы и дубли должны оставаться вне индекса.

## Контентные правила

- title кратко описывает конкретную страницу; бренд добавляется один раз шаблоном `— AniCast`, поэтому строка, уже содержащая бренд, задаётся через `title: { absolute }`;
- description — естественное резюме для человека, без перечисления вариантов одного ключа;
- один отчётливый H1 соответствует основной сущности страницы;
- structured data отражает только видимые и подтверждённые данные: `aggregateRating` использует тот же порог голосов, что и видимый бейдж, поэтому один-два голоса не публикуют рейтинг, которого на странице нет;
- JSON-LD сериализуется через `jsonLdScript`: значения приходят из внешнего импортёра, и `</script` внутри синопсиса не должен закрывать элемент;
- `numberOfEpisodes` публикуется только для episodic-шаблона; фильмы и другие одиночные единицы не получают завышенное значение из исторических provider-less part-строк;
- тайтлы связываются с персонажами, похожими работами и каталогом обычными `<a href>`;
- страницы без полезного содержимого не добавляются в sitemap.

## Следующий технический backlog

1. Добавить точный `updated_at` для тайтлов/персонажей в API и только после этого публиковать достоверный sitemap `lastmod`.
2. Добавить endpoint списка публичных коллекций, чтобы включать доступные подборки в sitemap.
3. Ввести отдельные URL для RU/EN до внедрения `hreflang`: cookie-перевод на одном URL не является самостоятельной языковой страницей.
4. Добавлять `VideoObject` только при наличии публичных правомерных watch URL, thumbnail, duration/uploadDate и реально доступного видео.
5. Подключить Search Console domain property через DNS и зафиксировать владельца процесса.
6. Вынести проверку диапазона пагинации до streaming-рендера Next.js, чтобы soft-404 отвечал твёрдым HTTP 404; до этого он исключается из индекса мета-тегом.
7. Нормализовать смешанную локальную/абсолютную нумерацию эпизодов отдельным dry-run процессом. Не удалять metadata-only строки автоматически: сначала отличить реальные будущие эпизоды и редакторские записи от импортных дублей.
8. Довести sitemap до полного покрытия: персонажи сейчас обрезаются лимитом `MAX_PAGES` × размера страницы backend'а, а франшизы, авторы, публичные коллекции и профили в документе отсутствуют.
9. SSR-контент для `/community`: сейчас лента приходит клиентским `useEffect`, из-за чего раздел отдаёт crawler'у пустую страницу и не создаёт входящих ссылок на публичные профили и коллекции.

## Ответственность

- разработка отвечает за HTTP-статусы, canonical/noindex, sitemap, structured data и релизный smoke;
- контент-оператор отвечает за названия, синопсисы, связи и качество посадочных страниц;
- владелец продукта раз в месяц принимает решения по кластерам запросов и приоритетам контента;
- доступы Search Console и DNS хранятся вне репозитория.

Базовые правила сверяются с официальной документацией Google Search Central: title links, canonicalization, robots/noindex, faceted navigation, pagination и sitemap.
