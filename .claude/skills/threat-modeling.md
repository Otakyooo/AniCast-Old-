# Threat Modeling

Анализ злоупотреблений, активов и границ доверия до реализации чувствительной функции.

## Процесс

1. Перечислить assets: sessions, personal data, catalog data, secrets и infrastructure access.
2. Определить actors, trust boundaries и entry points: browser, API, admin, worker и provider.
3. Для каждого boundary найти spoofing, tampering, unauthorized access, leakage, abuse и denial-of-service risks.
4. Связать риск с mitigation: auth, permission, validation, rate limit, isolation, logging и secret handling.
5. Проверить mitigation тестом и указать остаточный риск владельцу.

## Правила

- ID в URL не является авторизацией; проверять object-level permission.
- Не логировать cookies, tokens и sensitive payloads.
- Threat model дополняет `security-review.md`, но не заменяет его.
