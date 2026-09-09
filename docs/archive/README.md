# Архив проверок и решений по задачам

Материалы ниже сохраняют факты на дату написания. Это не действующие инструкции
для production; начать с [текущего состояния](../IMPLEMENTATION_STATUS.md) и
[эксплуатации](../OPERATIONS.md).

| Этап | Проверки |
| --- | --- |
| 08.09: бренд, workers, release gates | [Релиз](releases/RELEASE-2026-09-08.md) |
| 08.09: отдельный cache Redis | [Релиз](releases/RELEASE-2026-09-08-redis.md) |
| 09.09: firewall | [Релиз](releases/RELEASE-2026-09-09-firewall.md) |
| 09.09: registry и restore | [Релиз](releases/RELEASE-2026-09-09-registry.md) |
| 09.09: control, nonce, независимое восстановление | [Релиз](releases/RELEASE-2026-09-09-hardening.md) |
| 09.09: история RAM/CPU/swap | [Измерения](releases/RELEASE-2026-09-09-capacity.md) |
| 09.09: собственный OAuth | [Проверки](releases/RELEASE-2026-09-09-oauth.md) |
| 09.09: frontend security patch и npm gate | [Релиз](releases/RELEASE-2026-09-09-frontend-security.md) |
| 09.09: Next 16, две темы, логотип и админка | [Релиз](releases/RELEASE-2026-09-09-next16.md) |
| 09.09: API до workers, адаптивная шапка и мобильный hero | [Релиз](releases/RELEASE-2026-09-09-staged-design.md) |
| 09.09: React state, вход/плеер E2E и ограниченная нагрузка | [Релиз](releases/RELEASE-2026-09-09-react-scenarios.md) |
| 09.09: каталог, расписание, история и библиотека | [Релиз](releases/RELEASE-2026-09-09-tab-pages.md) |

Сохранены [аудит 08.09](audits/SYSTEM_AUDIT-2026-09-08.md),
[прежняя сводка](IMPLEMENTATION_STATUS-2026-09-07.md) и планы:
[страница тайтла](plans/1787709216153-home-discovery-polish.md),
[рекомендации](plans/1787745125782-recommendations-reasons-dismissals.md),
[кабинет/постеры](plans/cabinet-v3-and-poster-quality.md).
План не доказывает реализацию; подтверждение искать в коде и отчёте релиза.
