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
   замеры доступности/RTT, выбор хоста для API/БД и репетиция restore на отдельной
   машине. Полный перенос БД в этом релизе не выполняется.
2. **Redis: этап изоляции необязательного кеша.** Реализация и проверки описаны
   в [ADR 002](architecture/002-redis-isolation.md) и [отчёте](RELEASE-2026-09-08-redis.md).
   Broker, results и coordination state пока разделяют noeviction-инстанс;
   их заполнение остаётся риском. Добавлены отдельные метрики и предупреждение
   при превышении 80% maxmemory. Очереди и ключи ограничителей не очищаются.
3. **Средний: supply chain.** Базовые Docker tags изменяемые. Образы приложения
   фиксируются по digest/локальному image ID; CI registry publication уже есть,
   но переход на единый registry release flow требует эксплуатационной репетиции.
4. **Средний: CSP допускает unsafe-inline.** Caddy ограничивает источники, но
   inline XSS этим не устраняется. Исследовать nonce CSP и цену динамического
   рендеринга отдельным изменением с тестами плеера и авторизации.
5. **Firewall VPS: исправлено 09.09.2026.** Включена отдельная Anicast nftables
   table с проверенным public/tunnel SSH, ограничением INPUT и Docker forwarding.
   UFW остаётся inactive/masked. [Отчёт этапа](RELEASE-2026-09-09-firewall.md).
6. **Средний: полный векторный бренд-набор.** Компактный знак растровый; SVG,
   специальная ручная иконка 16 px и новое OG-изображение ещё не подготовлены.

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

Фактические результаты тестов и smoke-проверок: [отчёт релиза](RELEASE-2026-09-08.md).

## Дополнение этапа 2

У Prometheus обнаружено отсутствие доступа к bind-mounted metrics token: файл
600 принадлежал deployment user, процесс работает как nobody. Для monitoring
token-файлов установлены group 65534 и mode 640; env остались 600. Scrape после
исправления подтверждён фактическими Redis samples, добавлен verify-monitoring.sh.
