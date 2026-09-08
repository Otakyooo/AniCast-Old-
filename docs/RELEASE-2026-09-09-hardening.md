# Релиз: изоляция, восстановление и векторный бренд

Статус: приложения и эксплуатационные изменения выложены на обоих серверах.
Google consent и постоянный внешний сервер для API/БД пока ожидаются.

Изменения: отдельный control Redis с переносом TTL, nonce CSP, закреплённые Actions
и service images, Dependabot, проверки ошибок внешнего бэкапа, age recovery kit,
векторные SVG, favicon 16/32/48, social preview и страница Anicast Backups privacy.

Локально пройдены lint/typecheck/build и 73 frontend-теста. В изолированной среде
MainServer пройдены инфраструктурная валидация, backup failure gates и четыре фазы
Redis isolation (cache eviction/outage, control full/outage). Production DB и очереди
в этих проверках не изменялись.

На компьютере оператора расшифрован age-комплект, проверены хеши 11 конфигурационных
файлов и напрямую скачан из Drive прежний DB dump с совпадением SHA-256. Это
подтверждает независимый доступ к внешним копиям без MainServer. После смены OAuth
и release env комплект необходимо обновить и повторить проверку.

## Production и проверки

Приложения: `0b1147182a800e73d01f9cb7eea9f0a264581092`, artifact успешного
[CI 34287286284](https://github.com/Otakyooo/AniCast/actions/runs/34287286284).
Эксплуатационные изменения: `fb9f305e8f10f35976f4b085d9d4ee8d571fda83`;
backend/frontend/infrastructure проверки
[CI 34289747351](https://github.com/Otakyooo/AniCast/actions/runs/34289747351) пройдены.
Изменения только scripts/configs не требуют смены application images.

- Backend: `ghcr.io/otakyooo/anicast-backend@sha256:36e43aed61ae9b21c2cd54eb925ea10a7a2e87a66c2c4c9577be2704bd8143f7`.
- Frontend: `ghcr.io/otakyooo/anicast-frontend@sha256:f11140e3e72c30175ab911cf9a33f348dd953fe924b0a775f9ac15cc0c0364b5`.

Все восемь application/data services MainServer healthy, оба workers и три роли
Redis проверены. Перенесены и проверены 43 ключа control с остаточным TTL, очереди
не очищались. Source DB 2 сохранена. Image rollback использует новый control URL,
чтобы не вернуть устаревшие блокировки. Приватные topology/runtime snapshots:
MainServer `backups/predeploy-20260909-hardening`, VPS `/root/anicast-hardening-20260909`.
Три исходных удаления пользовательских PNG сохранены в production worktree.

В браузере проверены главная, каталог, переключение и сохранение светлой/тёмной
темы, отсутствие console errors и горизонтального переполнения текущего viewport.
39 изображений главной загружаются. Полная новая mobile/screen-reader/OS-theme
проверка в этом этапе не выполнялась; bootstrap/storage/system logic покрыта unit tests.
SVG/OG визуально проверены; metadata использует `og-v02.png`.
HTML получает отдельный nonce и private/no-store; Caddy сохраняет upstream CSP.
Style-атрибуты React разрешены отдельно. `/internal/metrics` снаружи отвечает 404.

Обнаружен и исправлен Docker hairpin: INPUT блокировал обращения frontend к
публичному HTTPS origin, кеш скрывал отказ холодных постеров. Разрешены только
web ports 80/443 с bridges; SSH/relay/metrics не открывались. После исправления
запрос изображения из контейнера: 200 за 1.55s вместо timeout. Проверены свежие
public/tunnel SSH и AWG/Docker rules. `.gitattributes` закрепляет LF, устраняя
ошибку CRLF при упаковке Linux scripts/configs на Windows.

## Бэкапы и репетиция восстановления

Свежие DB/media выгружены в gdcrypt с checksum sidecars и offsite success markers.
Установлено расписание UTC: DB каждые 6h в :15, media ежедневно 03:45,
recovery-kit по воскресеньям 05:05, freshness exporter каждые 5 минут.
Прежние restore-verify и maintenance entries сохранены. Freshness alerts:
DB >7h, media >26h, kit >8d; отдельно — остановка экспорта метрик.
Ручные backup tests использовали BACKUP_NOTIFY=0.

Обновлённые age-комплекты (MainServer 21 файл, VPS 11) загружены в gdcrypt и
скопированы на компьютер. Расшифровка и все hashes там проверены без открытых
файлов; ключ расшифровки на серверы не передавался. Прямые Drive download и SSH
на VPS с Windows доказали доступ без MainServer.

Полный успешный DR прогон использовал текущий backend digest, DB dump от 08.09
03:15 UTC и media от 06.09 03:45 UTC. Восстановлены 54 таблицы, 100 тайтлов,
7 647 изображений / 378 537 499 байт; все 100 постеров доступны. Пройдены session
login, защищённый API, одноразовый password reset, email в памяти, Telegram capture
sink и signed playback issue/resolve. Отдельный Caddy переключён на реальный
восстановленный HTTP API и обратно; публичный маршрут не менялся. Временные
containers/volumes/network удалены. Восстановление и проверки: **142.16s**, без
скачивания файлов/images. Реальная доставка людям и стороннее видео не проверялись.
Это не измерение полного RTO от аварии до публичного переключения.

## Что ещё требует действий владельца

Google app Anicast Backups опубликовано в Production, Drive API включён,
Desktop client создан, секрет сохранён приватно; неиспользуемый первоначальный
секрет отключён. Защитный экран непроверенного приложения должен пройти владелец.
До этого production rclone сохраняет прежний рабочий клиент. После consent нужны
refresh/read/write check, атомарная смена config и обновление age-комплектов.

Для постоянного переноса API/БД нужен внешний хост. На VPS 961 MiB весь стек
постоянно не переносился; после работ available около 486 MiB. Новый control Redis
использует около 2.4 MiB при лимите 96 MiB. На MainServer короткий vmstat замер не
показал swap-out, swap-in почти отсутствовал. Увеличение до 2 CPU / 4 GiB даст
запас, но зависимость от дома устранит перенос data tier.

Цели RPO 6/24h действуют при успешном offsite; цель RTO 2h требует доступного хоста
и ключей. Физическая запасная копия личного ключа и DNS-account recovery не
проверялись; текущий план сохраняет тот же VPS/DNS. [Runbook](RECOVERY_AND_MIGRATION.md),
[ADR 005](architecture/005-control-and-offline-recovery.md). Ops skill прошёл quick_validate.py.
