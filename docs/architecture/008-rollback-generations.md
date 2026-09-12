# ADR 008: три поколения откатов и gate необратимых миграций

Дата: 2026-09-12. Статус: принято, zero-budget (без новых хостов и сервисов).

## Контекст

`scripts/deploy.sh` хранил одно поколение отката (`current.env` →
`previous.env`). Второй подряд битый релиз затирал последний известный хороший
манифест. Проверки образа (`makemigrations --check`) ловили только отсутствие
миграций, но не необратимость (`RemoveField`, `NOT NULL` без default):
image-only rollback при новой схеме давал 500 до ручного восстановления.
См. [ADR 004](004-registry-and-recovery.md) (immutable digests/env) и
[ADR 007](007-staged-rollout.md) (API first, bulk grace 1900s).

## Решение

1. Ротация трёх поколений в `scripts/deploy.sh`: `previous.env`,
   `previous-2.env`, `previous-3.env`. `scripts/rollback.sh` принимает опциональный
   снапшот (`previous-2.env` / `previous-3.env`, bare name или путь).
   База `previous.env` сохранена: поведение по умолчанию не изменилось.
2. `scripts/check-migration-safety.sh` (+ CI gate после `makemigrations --check`)
   падает на `RemoveField` / `RemoveModel` / `DeleteModel`, `RunSQL` без reverse
   и `AlterField` с `null=False`, пока миграция не названа в
   `MIGRATION_BREAKING_APPROVED="<app>.<migration>,..."` с отдельным
   maintenance/restore-планом. Эвристика, а не доказательство безопасности:
   `expand/contract` остаётся обязанностью автора.
3. Ранбук: [Deployment](../operations/DEPLOYMENT.md#automatic-rollback).

## Что заменяет

Дополняет ADR 004 (поколения снапшотов) и ADR 007 (условия применимости
автоотката). Топологию Compose, имена проектов/волюмов и содержимое БД откат
по-прежнему не трогает.

## Проверка

- `sh scripts/check-migration-safety.sh origin/main` — pass на текущей истории.
- `sh -n scripts/deploy.sh scripts/rollback.sh` — синтаксис.
- Полный deploy/rollback-тест — в изолированном CI (`scripts/tests/deploy_rollback_test.sh`
  через `scripts/validate.sh`), не на production.
