# Этап 4: registry и восстановление вне MainServer

Дата: 09.09.2026, время пользователя Europe/Moscow.

## Поставка

Приложения собраны в GitHub Actions и опубликованы после всех проверок.
[Успешный запуск CI/publish](https://github.com/Otakyooo/AniCast/actions/runs/34281338091).
Исходники релиза: `ea3b19032b67ba740aad81a0c52ba10194a77456`.
Этот commit и предыдущие этапы отправлены в приватный GitHub repository.
Последующее дополнение содержит media drill и документацию; приложение в
production соответствует указанному выше release SHA.

| Компонент | GHCR image digest |
| --- | --- |
| `ghcr.io/otakyooo/anicast-backend` | `sha256:607e1c13f28ddff2817f51562ce19f59e4d9a84f0d9dffbbcd1e9630ade591c0` |
| `ghcr.io/otakyooo/anicast-frontend` | `sha256:4437939985e8bf13b421131acceed2aa96d8b02eb51e94ee17cd7d84eb3755d1` |

CI: backend pytest/ruff/mypy/Django checks/pip-audit; frontend lint/typecheck/tests/
build; Compose, monitoring rules, Redis isolation, реальные nftables netns,
deploy/rollback regression, три проверки release manifests, сборки и Caddy validation.
Actionlint проверил оба workflow. Исправлен удвоенный `sha256:` в старой подсказке
для manifest; неполные digest теперь отвергаются.

## Выкладка

MainServer: свежий предрелизный дамп 3 537 166 байт проверен `pg_restore --list`.
Compose и manifest сохранены в `backups/predeploy-20260909-registry/`.
Runtime env — прежний неизменяемый снимок Redis-релиза. PostgreSQL и оба Redis
не пересоздавались; обновлены только backend, два workers и beat.
Все healthchecks, отдельный ping каждому worker и мониторинг прошли.

VPS: Compose, исходный manifest и приватный снимок env находятся в
`/root/anicast-registry-20260909/`. Новый release и baseline отката используют
этот неизменяемый env. Постоянных сервисов и сборок на VPS не добавлено.
Frontend и Caddy healthy; public home и titles API — 200, `/internal/metrics` —
404. Firewall verification прошёл. После выкладки доступно 478 MiB памяти,
frontend занимает около 76 MiB. Главная проверена в реальном браузере: каталог
и сохранённая светлая тема отображаются, варианты темы доступны в шапке.
Предыдущие локальные образы сохранены на обоих хостах; registry-to-local rollback
проверен в изолированном shell regression, production принудительно не откатывался.

## Восстановление из внешнего backup

Использованы файлы, скачанные через rclone crypt из Google Drive, не локальные
производственные тома. SHA-256 совпали с исходными локальными backup:

| Копия | Дата UTC | SHA-256 |
| --- | --- | --- |
| DB | 08.09.2026 03:15:01 | `444b482a373cb3e45fdc728fa7dd85077201be6d20102c4d4878ccb86ae6f328` |
| Media | 06.09.2026 03:45:01 | `a6506c3419280472f30a15c9db663626ae061f036abb644b009c7a74baf25b47` |

На VPS выполнен `scripts/restore-isolated.py` с опубликованным backend образом
и заранее загруженным PostgreSQL 17. Свежая БД и media volume изолированы от
production. Проверки API выполнялись с правами только чтения.

- Восстановлено 54 таблицы, 3 пользователя, 100 тайтлов, 4 записи библиотеки,
  27 записей прогресса; незавершённых миграций и непроверенных FK нет.
- Готовность, каталог, карточка, библиотека, история и media API ответили 200.
- 7 647 изображений, 378 537 499 распакованных байт. Постеры всех 100 тайтлов
  присутствуют; отсутствующих ссылочных постеров тайтлов — 0. Это не проверка
  каждой ссылки на портреты персонажей/создателей.
- Restore + smoke: **93.13 секунды**, без времени скачивания файлов/образов.
- Первый запуск остановлен до создания ресурсов из-за MemAvailable ниже 448 MiB.
  После завершения загрузок доступно 487 MiB; повторный запуск прошёл с тем же
  порогом. После очистки доступно 486 MiB. Временных контейнеров, volumes и сетей нет.

## Ограничения и следующий этап

DB snapshot старше момента проверки примерно на 18.5 часа; media — на два дня
старше DB. Это свойства текущего расписания backup, а не нулевой RPO. Полное
переключение трафика, внешнее воспроизведение и реальные auth/notification flows
при восстановлении не выполнялись.

MainServer остаётся единой точкой отказа. Репетиция доказывает переносимость
данных и приложения, но не готовность слабого VPS постоянно обслуживать весь стек.
Нужен отдельный план восстановления credentials/crypt keys без доступа к MainServer
и переход rclone на собственный Google OAuth client до отключения общего клиента.
Текущая загрузка из внешнего хранилища подтверждена; миграция OAuth не выполнена.

Решение и ресурсные ограничения: [ADR 004](../../architecture/004-registry-and-recovery.md).
