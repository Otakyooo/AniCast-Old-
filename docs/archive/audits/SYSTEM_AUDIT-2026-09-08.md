# Аудит Anicast: 08.09.2026

Область: исходники и конфигурация, Docker на обоих серверах, ресурсы, история
релизов, резервные копии, проверки приложения. Это инженерный аудит, не внешний пентест.

## Подтверждённые проблемы и исправления этого релиза

| Приоритет | Наблюдение | Изменение / проверка |
| --- | --- | --- |
| Высокий | Production project names `mainserver`/`vps` отличались от defaults `anicast-mainserver`/`anicast-vps`; новый деплой мог создать пустые volumes | Defaults приведены к живым именам; существующие override сохранены; манифест текущего образа обязателен до первого релиза |
| Высокий | Один worker слушал все 6 очередей без явного ограничения concurrency | Разделены уведомления/default и providers/posters/maintenance/analytics; по одному процессу, отдельные лимиты и healthchecks |
| Средний | VPS frontend выполнялся от root, без memory limit (`Config.User` пустой, `HostConfig.Memory=0`) | USER node, 512 MiB, Node heap 320 MiB, no-new-privileges, init |
| Средний | Next image cache внутри заменяемого контейнера терялся при релизе | Отдельный volume только для `.next/cache/images`; HTML/data cache между сборками не переносится |
| Средний | `next lint` в package.json при Next 15.5 и имеющемся flat eslint config | Прямой запуск `eslint .` |
| Средний | Документ бренда описывал старую синюю/коралловую палитру и удалённый источник маскота | Новая спецификация и единые токены по PDF, обе темы, новые растровые ассеты |
| Средний | Production check в deploy не превращал Django warnings в провал | `check --deploy --fail-level WARNING` |

При строгом production check дополнительно обнаружено security.W009: ключ подписи
44 символа (значение не выводилось). Релиз включает генерацию нового случайного
ключа; существующие сессии/подписанные ссылки могут потребовать повторного входа.

## Ресурсы и устойчивость

Снимок начала аудита: MainServer RAM 2582 MiB, available 768 MiB, swap 4396/6143 MiB;
VPS RAM 961 MiB, available 416 MiB, swap 62/2047 MiB. Swap сам по себе не доказывает
активный thrashing: для этого нужны временные ряды swap-in/out и latency.
Свободный диск: 66 GiB на MainServer, 37 GiB на VPS. Контейнеры в начале аудита healthy.
Дамп БД от 08.09, 03:15 UTC, 3 498 650 байт; наличие файла не равно успешному восстановлению.

## Оставшиеся риски

1. **Высокий: единая точка отказа.** Домашний MainServer, питание, канал и туннель
   находятся на пути API. Разделение очередей этого не устраняет. Следующий этап:
   замеры доступности/RTT и выбор хоста для API/БД. Репетиция DB/media restore
   вне MainServer успешно выполнена 09.09; полный перенос и переключение трафика
   не выполнялись. [Отчёт](../releases/RELEASE-2026-09-09-registry.md).
2. **Redis: изоляция реализована 09.09.** Broker/results, control и ephemeral
   имеют отдельные инстансы. Перенесены и проверены 43 ключа с TTL; источник не
   очищался. Три роли наблюдаются независимо. AOF и noeviction не заменяют
   репликацию: потеря диска MainServer по-прежнему затронет очереди.
3. **Supply chain:** Actions и все service images закреплены SHA/digest;
   Dependabot настроен. apt-пакеты внутри сборок не закреплены индивидуально,
   поэтому побитовая воспроизводимость сборки не заявляется.
4. **CSP:** production scripts требуют nonce, inline handlers запрещены.
   Числовые React style-атрибуты оставлены разрешёнными. Проверены реальный
   браузер, темы и HTTP-заголовки; это не доказательство отсутствия любого XSS.
5. **Firewall:** после отдельной проверки исправлен Docker hairpin к публичным
   80/443. Кеш постеров скрывал отказ холодной загрузки. SSH/relay/metrics не
   открывались для Docker; внешние ограничения сохранены.
6. **Бренд:** подготовлены SVG полного маскота, компактный знак, lockup,
   отдельный favicon 16 px и новое OG. Оригинальная иллюстрация сохранена.
7. **Recovery credentials:** с Windows расшифрован age-kit и напрямую из Drive
   скачаны DB/media с проверкой SHA-256; SSH на VPS работает без MainServer.
   Собственный OAuth-клиент активирован после Google consent; forced refresh,
   новая внешняя копия БД и оба обновлённых age-kit проверены с Windows.
   [Проверки OAuth](../releases/RELEASE-2026-09-09-oauth.md).
   DNS-account не архивирован; текущая схема переноса сохраняет тот же VPS и DNS.

Сводка проверок и актуальные ограничения: [hardening release](../releases/RELEASE-2026-09-09-hardening.md).

## Положительные подтверждённые свойства

PostgreSQL и Redis не публикуют порты хоста; backend слушает адрес туннеля.
Monitoring изолирован от data network; есть auth для Redis и metrics.
Реализованы ротация логов, DB backup/restore scripts, регулярные дампы, healthchecks,
ограниченные provider probes и API timeouts, CI проверки и rollback scripts.
Секреты не выводились в отчёт; отсутствие утечек во всей истории git не доказано.

## Основания решений

- [Celery: prefetch и разделение длительных/коротких задач](https://docs.celeryq.dev/en/stable/userguide/optimizing.html).
- [Next.js 15: self-hosting](https://nextjs.org/docs/15/app/guides/self-hosting).
- [Docker: контейнеризация Next.js](https://docs.docker.com/guides/nextjs/).

Фактические результаты тестов и smoke-проверок: [отчёт релиза](../releases/RELEASE-2026-09-08.md).

## Дополнение этапа 2

У Prometheus обнаружено отсутствие доступа к bind-mounted metrics token: файл
600 принадлежал deployment user, процесс работает как nobody. Для monitoring
token-файлов установлены group 65534 и mode 640; env остались 600. Scrape после
исправления подтверждён фактическими Redis samples, добавлен verify-monitoring.sh.
