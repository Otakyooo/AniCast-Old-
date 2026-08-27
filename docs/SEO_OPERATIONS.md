# AniCast — SEO-процесс и технический контроль

Версия: 1.0
Дата: 27 августа 2026

## Цель

SEO для AniCast — это управляемый цикл «доступность → индексирование → качество сниппета → полезный переход», а не разовая расстановка meta-тегов. Приоритетные посадочные страницы: главная, каталог и его пагинация, расписание, тайтлы, персонажи, сообщество, медиа и публичные коллекции.

## Матрица индексирования

| Группа URL | Политика | Причина |
| --- | --- | --- |
| `/`, `/catalog`, `/catalog?page=N`, `/schedule`, `/community`, `/media` | `index, follow`, self-canonical | Самостоятельные публичные страницы |
| `/titles/<slug>`, `/characters/<slug>` | `index, follow`, self-canonical | Основной энциклопедический контент |
| `/collections/<owner>/<slug>` | `index, follow`, self-canonical | Публичная авторская подборка с SSR-контентом |
| `/users/<public_id>` | `index, follow`, self-canonical | Только явно включённый публичный профиль с SSR-коллекциями и рецензиями |
| Поиск, сортировка и фильтры `/catalog?...` | `noindex, follow`, canonical на `/catalog` | Не создавать индекс из комбинаций фасетов |
| Архивные недели `/schedule?week=...` | `noindex, follow`, canonical на `/schedule` | Не создавать бесконечный календарь |
| Watch и отдельные эпизоды | `noindex, follow`, canonical на тайтл | Дублируют основную карточку тайтла |
| Account, library, history, notes, settings, recommendations, auth, управление коллекциями | `X-Robots-Tag: noindex, follow` | Личные или служебные HTML-страницы |
| `/api/`, `/staff`, `/auth` callbacks | `Disallow` в `robots.txt` | Служебные маршруты, не являющиеся посадочными |

`robots.txt` не используется как замена `noindex`: crawler должен получить HTML или HTTP-заголовок, чтобы удалить URL из индекса.

## Релизный gate

Каждый frontend-релиз проходит:

1. `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`;
2. `robots.txt` содержит production sitemap и не блокирует индексируемые страницы;
3. sitemap отвечает `200`, содержит только canonical URL и не содержит личных/фильтрованных/watch URL;
4. шаблоны `/`, `/catalog`, `/titles/<slug>`, `/characters/<slug>` имеют уникальные title, description и canonical;
5. личная страница возвращает `X-Robots-Tag: noindex, follow`;
6. обычный missing route отвечает HTTP 404; вышедшая за диапазон пагинация не менее обязана отдавать `noindex` и canonical на базовый каталог;
7. JSON-LD валиден и совпадает с видимым контентом;
8. public smoke не показывает 5xx, firing alerts отсутствуют.

Минимальный smoke после production-деплоя:

```bash
curl -fsS https://anicast.online/robots.txt
curl -fsS https://anicast.online/sitemap.xml >/dev/null
curl -fsSI https://anicast.online/account | grep -i x-robots-tag
curl -fsS https://anicast.online/titles/21-one-piece | grep -E 'canonical|application/ld\+json'
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

- title кратко описывает конкретную страницу; бренд добавляется один раз шаблоном `— AniCast`;
- description — естественное резюме для человека, без перечисления вариантов одного ключа;
- один отчётливый H1 соответствует основной сущности страницы;
- structured data отражает только видимые и подтверждённые данные;
- тайтлы связываются с персонажами, похожими работами и каталогом обычными `<a href>`;
- страницы без полезного содержимого не добавляются в sitemap.

## Следующий технический backlog

1. Добавить точный `updated_at` для тайтлов/персонажей в API и только после этого публиковать достоверный sitemap `lastmod`.
2. Добавить endpoint списка публичных коллекций, чтобы включать доступные подборки в sitemap.
3. Ввести отдельные URL для RU/EN до внедрения `hreflang`: cookie-перевод на одном URL не является самостоятельной языковой страницей.
4. Добавлять `VideoObject` только при наличии публичных правомерных watch URL, thumbnail, duration/uploadDate и реально доступного видео.
5. Подключить Search Console domain property через DNS и зафиксировать владельца процесса.
6. Вынести проверку диапазона пагинации до streaming-рендера Next.js, чтобы soft-404 отвечал твёрдым HTTP 404; до этого он исключается из индекса мета-тегом.

## Ответственность

- разработка отвечает за HTTP-статусы, canonical/noindex, sitemap, structured data и релизный smoke;
- контент-оператор отвечает за названия, синопсисы, связи и качество посадочных страниц;
- владелец продукта раз в месяц принимает решения по кластерам запросов и приоритетам контента;
- доступы Search Console и DNS хранятся вне репозитория.

Базовые правила сверяются с официальной документацией Google Search Central: title links, canonicalization, robots/noindex, faceted navigation, pagination и sitemap.
