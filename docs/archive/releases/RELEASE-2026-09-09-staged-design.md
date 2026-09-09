# 09.09.2026: последовательный rollout и первый этап улучшения дизайна

Application/rollout commit: `74ca868033178335dd1a35efff42609c4880e8f6`.
[Полный publish CI 34347560556](https://github.com/Otakyooo/AniCast/actions/runs/34347560556)
успешен. Последующий host-only commit `8ba542c` добавляет новый helper в recovery
kit; application image contexts этим изменением не затронуты.

| Production | Проверенный CI digest |
| --- | --- |
| Backend | `ghcr.io/otakyooo/anicast-backend@sha256:7465c3d37e27f962a713da213448428e5a8d4881041f74a86cff17553ced85a2` |
| Frontend | `ghcr.io/otakyooo/anicast-frontend@sha256:98de16613ffad7c42dd8174421a6d157fe8f721a1a0434b7bdb7d3c282d470aa` |

## Развёртывание

Deploy и rollback используют общий start-release: data + API и readiness gate,
затем default/beat, затем bulk. Worker-фазы не пересоздают API (`--no-deps`).
Bulk grace/stop timeout — 1900s вместо 600s, чтобы покрыть имеющийся hard limit
1800s. Default остаётся 600s. [ADR 007](../../architecture/007-staged-rollout.md).

Shell state-machine тест прошёл для успешного rollout и сбоев API/default/bulk,
с восстановлением предыдущего API до workers. Docker CI создал отдельный Compose
project, медленно завершал старый bulk и получил 7 успешных HTTP-ответов нового
API до выхода worker. Тестовые контейнеры/сеть удалены; production DB/очереди и
сообщения людям не использовались.

На MainServer этап API стал healthy до начала worker rollout. Default/beat и
bulk затем прошли health gates без ручного запуска. Долгого активного bulk в
этом релизе не наблюдалось; длительный drain воспроизведён в CI. StopTimeout
реального bulk-контейнера подтверждён: 1900. VPS deploy/verify тоже успешны.

Сохранены приватные Compose/env/manifest снимки. Immutable runtime env не менялись,
RAM limits/concurrency не увеличивались; PostgreSQL и три Redis продолжили работу
без пересоздания (uptime 13h), миграций схемы не было. Три прежних удаления PNG
в Main checkout сохранены.

Параллельный HTTP sampler с Main обращался к недоступному с этого хоста адресу
10.78.0.2:8000; таймаут воспроизводится и после успешного релиза. Его семь нулевых
результатов исключены из оценки downtime. Точную длительность production-паузы
этим sampler не измерили. Readiness внутри контейнеров и публичный API успешны;
из этого не следует нулевой downtime единственного API-контейнера.

## Дизайн и браузерные проверки

- На 768–1439 px навигация вынесена во вторую строку; все шесть ссылок доступны.
  Поиск остаётся полноценным полем, его Escape/focus breakpoint совпадает с CSS.
- На телефоне поле поиска открывается внутри viewport и возвращает фокус на
  кнопку после Escape. Отступ якоря плеера учитывает высоту шапки.
- Небольшой постер и заголовок мобильного тайтла стоят рядом, основные действия
  идут полной строкой. В production при 390 px верх действий — примерно 337 px.
- Кнопки озвучки имеют высоту не менее 44 px и основной цвет текста.

CI: 73 unit tests, 16 Chromium E2E на 1440/1280/820/390 px, lint/typecheck/build,
security audits, backend и infrastructure gates. Остались прежние 18 React effect
warnings; остальные lint errors блокируют CI. Сборка локально прошла с heap 768 MiB.

Визуальная static preview и затем реальный production проверены в обеих темах
на всех четырёх ширинах: нет горизонтального переполнения, перекрытых ссылок или
кнопок озвучки ниже 44 px; мобильный поиск и возврат фокуса прошли. Финальные
скриншоты сделаны с reduced motion, чтобы оценивать конечные цвета после смены
темы. Полный сценарий плеера/входа эта проверка не покрывает.

Финальный public smoke: home 200 / 0.892s, titles API 200 / 0.581s,
`/internal/metrics` 404. Все контейнеры с healthcheck на Main/VPS healthy.

## Backups и ресурсы

Предрелизный dump: `anicast-20260909T115242Z.dump`, 3 565 439 bytes,
SHA-256 `8540f9ba36f48bd193a199648d2fbce9f32c77e31b9602cc5abac0efc4de6c9b`.
Локальная проверка backup script и независимое скачивание из Drive успешны;
полного повторного restore в этом релизе не выполняли.

Новые kits `20260909T115938Z`: 22 файла MainServer / 12 VPS. Все hashes проверены
операторским ключом вне серверов; обе копии из Drive совпали с локальными age.
Current image manifests и байты `scripts/start-release.sh` внутри обоих kits
сверены с релизом. Временный plaintext config/скачанные проверочные файлы удалены.
Ручные backups использовали `BACKUP_NOTIFY=0`.

Перед релизом MainServer: 3606 MiB RAM, около 1999 MiB available; один CPU.
В окне 10:49–11:49 UTC minimum available 1955.598 MiB, max CPU busy (5m) 18.911%,
VPS minimum available 442.871 MiB из 961 MiB. Замеры включают обслуживание и не
определяют предельное число зрителей. Внешний data host/HA и нагрузочный профиль
остаются отдельной работой.
