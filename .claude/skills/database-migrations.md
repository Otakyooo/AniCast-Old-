# Database Migrations / Persistence Audit

PostgreSQL, миграции, транзакции, целостность данных.

## Проверки

1. **Миграции**: каждая миграция обратима, идемпотентна, безопасна для production данных
2. **Транзакции**: атомарные операции используют `transaction.atomic()`, нет partial writes
3. **Индексы**: добавлены для частых запросов, без лишней нагрузки на writes
4. **Constraints**: NOT NULL, UNIQUE, FK — на уровне БД, не только валидацией
5. **Объём данных**: миграции учитывают существующие записи (ALTER TABLE на больших таблицах)

## Django-специфика

```python
# Безопасная миграция
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("titles", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="title",
            name="status",
            field=models.CharField(max_length=20, default="ongoing"),
        ),
    ]
```

## Антипаттерны

- DROP TABLE без backup
- Миграция без `default` на NOT NULL поле
- Нет rollback-плана для destructive migrations
- Raw SQL без review DBA/архитектора