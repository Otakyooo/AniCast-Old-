from django.urls import path

from .views import (
    csrf,
    current_user,
    register,
    sign_in,
    sign_out,
    telegram_challenge,
    telegram_challenge_complete,
    telegram_webhook,
)

urlpatterns = [
    path("auth/csrf/", csrf, name="auth-csrf"),
    path("auth/register/", register, name="auth-register"),
    path("auth/login/", sign_in, name="auth-login"),
    path("auth/logout/", sign_out, name="auth-logout"),
    path("auth/me/", current_user, name="auth-me"),
    path("auth/telegram/challenge/", telegram_challenge, name="auth-telegram-challenge"),
    path("auth/telegram/challenge/complete/", telegram_challenge_complete, name="auth-telegram-complete"),
    path("auth/telegram/webhook/", telegram_webhook, name="auth-telegram-webhook"),
]
