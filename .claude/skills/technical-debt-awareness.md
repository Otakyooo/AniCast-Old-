# Technical Debt Awareness

Явное выявление, оценка и фиксация временных решений и их цены.

## Процесс

1. Найти shortcuts, TODO, compatibility shims, duplicated logic и ручные операции.
2. Для каждого указать причину, owner, impact и условие погашения.
3. Оценить риск: correctness, security, performance, operability и стоимость изменений.
4. Записать debt в задачу или decision log, а не оставлять только комментарий.
5. Не называть нормальное простое решение долгом без будущей стоимости.

## Правило

Debt, влияющий на данные, auth или rollback, блокирует release либо требует явного принятия риска владельцем.
