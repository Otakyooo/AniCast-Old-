# ADR 007: запуск API до завершения фоновых workers

Дата: 09.09.2026. Уточняет порядок deploy/rollback из ADR 004, топология прежняя.

В предыдущем релизе единый Compose up пересоздал API, но отложил его запуск до
завершения старого bulk worker. Очередь тяжёлых задач не должна определять время
недоступности API.

Deploy и rollback используют один `scripts/start-release.sh`. Первая фаза запускает
PostgreSQL, три Redis и backend; Compose ждёт readiness до 120s. Вторая обновляет
default worker и beat, третья — bulk. Обе worker-фазы используют `--no-deps`;
неуспешная фаза останавливает rollout и запускает существующий image rollback.
Общий итоговый verify-deploy остаётся обязательным перед promotion manifest.

Default worker сохраняет grace 600s. Для bulk — 1900s: его максимальный hard task
limit равен 1800s. Явный stop timeout в rollout применяется также к старому
контейнеру, который ещё создан с grace 600s. Принудительное сокращение ожидания
ради скорости релиза не используется.

Один backend при пересоздании всё ещё имеет короткое окно недоступности. Новая
версия API некоторое время работает со старыми workers; schema/task payloads
должны быть совместимы между соседними релизами. Новые сервисы, дополнительная
RAM и worker concurrency не требуются. MainServer не удаляет неизвестные orphan
containers автоматически; смена топологии требует отдельного изменения.

Проверки: shell state machine для успешного релиза и ошибок API/default/bulk с
реальным rollback entry point; Docker drill на одноразовом Compose project с
медленно завершающимся bulk и HTTP-пробами нового API. Тест не использует production
DB, очереди, порты или сообщения пользователям.
