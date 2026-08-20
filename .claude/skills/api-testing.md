# API Testing

DRF API, контрактные тесты, проверка интеграции frontend ↔ backend.

## Процесс

1. **Контракт**: зафиксировать ожидаемый request/response формат (status code, body schema, headers)
2. **Тесты**:
   - Happy path: корректный запрос → ожидаемый ответ
   - Validation: невалидные данные → 400 с описанием ошибки
   - Auth: неавторизованный доступ → 401/403
   - Edge cases: пустые списки, пагинация, несуществующие ID
3. **Контрактные тесты**: frontend и backend согласованы по схеме API
4. **Integration**: реальный HTTP-запрос через Django test client

## Пример

```python
from rest_framework.test import APIClient

def test_create_title_requires_auth():
    client = APIClient()
    resp = client.post("/api/v1/titles/", {"name": "Test"})
    assert resp.status_code == 403

def test_create_title_valid(authenticated_client):
    resp = authenticated_client.post("/api/v1/titles/", {"name": "Naruto", "status": "ongoing"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Naruto"
```

## Правила

- Каждый endpoint покрыт минимум 3 тестами: success, validation error, auth error
- Response schema проверяется целиком, не только отдельные поля
- Пагинация тестируется: пустая страница, последняя страница, вне диапазона