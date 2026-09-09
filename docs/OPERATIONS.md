# Эксплуатация Anicast

Актуальные настройки сверять с Compose, immutable release env и
[текущим состоянием](IMPLEMENTATION_STATUS.md). Все команды в разделах выполняются
из корня репозитория на указанном хосте, если не оговорено иначе.

| Задача | Инструкция |
| --- | --- |
| Выпустить релиз, проверить, откатить | [Deployment](operations/DEPLOYMENT.md) |
| Бэкапы, собственный OAuth, независимое восстановление, перенос API/БД | [Backups](operations/BACKUPS.md) |
| Метрики, RAM/CPU, три Redis, firewall и Telegram relay | [Monitoring](operations/MONITORING.md) |
| Каталог, импорт, SMTP, права, кеширование, CSP и API | [Application](operations/APPLICATION.md) |

Production: MainServer `/home/lama_admin/anicast`, VPS `/opt/anicast`.
Compose project names — `mainserver` и `vps`. На VPS нет git; конфигурация
синхронизируется отдельно от образов. Секреты находятся в приватных файлах хостов,
а release manifests содержат идентификаторы образов и пути к env.

Образы собираются в CI и разворачиваются по digest. При изменении только
документации/skills достаточно синхронизации файлов; приложение не перезапускается.
Проверки определяются изменённым слоем, полный CI описан в Deployment.

Репетиция восстановления не является production restore. Бэкап считается внешним
после успешной выгрузки; age-комплект должен быть доступен вне MainServer и Drive,
поскольку содержит ключи для доступа к Drive. Подробнее — в Backups.

Замеры, инциденты и конкретные релизы сохранены в [архиве](archive/README.md).
