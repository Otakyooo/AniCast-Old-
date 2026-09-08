# Документация Anicast

Начать с [текущего состояния](IMPLEMENTATION_STATUS.md).

| Вопрос | Документ |
| --- | --- |
| Что и как эксплуатируется | [OPERATIONS](OPERATIONS.md) |
| Что нашли в системе | [Аудит 08.09.2026](SYSTEM_AUDIT-2026-09-08.md) |
| Запас RAM/CPU и история нагрузки | [Ресурсы 09.09.2026](RELEASE-2026-09-09-capacity.md) |
| Собственный OAuth и свежие recovery kits | [OAuth 09.09.2026](RELEASE-2026-09-09-oauth.md) |
| Почему и как меняется архитектура | [ADR 001](architecture/001-stability-first.md), [Redis: ADR 002](architecture/002-redis-isolation.md), [Firewall: ADR 003](architecture/003-vps-firewall.md), [Registry/restore: ADR 004](architecture/004-registry-and-recovery.md), [Control/offline: ADR 005](architecture/005-control-and-offline-recovery.md) |
| Последний релиз и проверки | [Hardening](RELEASE-2026-09-09-hardening.md), [Registry и восстановление](RELEASE-2026-09-09-registry.md), [Firewall VPS](RELEASE-2026-09-09-firewall.md), [Redis](RELEASE-2026-09-08-redis.md), [бренд](RELEASE-2026-09-08.md) |
| Цвета, темы, маскот | [Бренд](BRAND_UI_TECH_SPEC.md), [исходный PDF](Anicast-Brand-Guide-v01.pdf) |
| Поведение и доступность UI | [Правила интерфейса](FRONTEND_DESIGN_RULES.md) |
| Каталог и плеер | [TITLE_DATA_AND_PLAYER](TITLE_DATA_AND_PLAYER.md) |
| Поисковая индексация | [SEO_OPERATIONS](SEO_OPERATIONS.md) |
| Аналитика посещений | [VISIT_ANALYTICS](VISIT_ANALYTICS.md) |
| Инструкции агентам | [AGENTS.md](../AGENTS.md), [Система skills](AGENT_SKILLS.md) |

`archive/` хранит исторические сведения. При изменении поведения обновлять
соответствующий документ, а не дописывать новый статус к старому тысячестрочному журналу.
Секреты, дампы БД, токены и приватные URL источников сюда не помещать.
