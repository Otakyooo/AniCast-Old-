# Релиз: изоляция, восстановление и векторный бренд

Статус: подготовлен; до успешного CI и production-проверок не считать выложенным.

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

OAuth и production-переход ещё не подтверждены этим отчётом. Внешний постоянный
сервер для API/БД пока не предоставлен. См. [ADR 005](architecture/005-control-and-offline-recovery.md).
