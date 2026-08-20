# Security Review

Auth, cookies, CSRF, secrets, permissions — проверка безопасности перед merge.

## Проверки

1. **Аутентификация**: SessionAuthentication, CSRF-токен, secure cookies
2. **Авторизация**: permissions на каждом endpoint, нет обходов через IDOR
3. **Секреты**: ничего в коде, только env vars, `.env` в `.gitignore`
4. **Input validation**: serializer validation, SQL injection, XSS
5. **Cookies**: `HttpOnly`, `Secure`, `SameSite=Lax`
6. **CORS/CSRF**: `CSRF_TRUSTED_ORIGINS` ограничен, не `*`
7. **Rate limiting**: чувствительные endpoints защищены от abuse
8. **Headers**: `X-Frame-Options: DENY`, `Content-Type-Nosniff`

## Django/DRF-специфика

```python
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
```

## Вопросы

- Можно ли получить чужие данные через manipulation ID?
- Можно ли обойти auth через прямой URL?
- Что произойдёт при expired/invalid session?
- Есть ли sensitive data в логах или error responses?
