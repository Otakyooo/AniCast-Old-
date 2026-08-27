from django.urls import path

from .views import (
    account_summary,
    csrf,
    current_user,
    profile_settings,
    register,
    sign_in,
    sign_out,
    telegram_challenge,
    telegram_challenge_complete,
    telegram_webhook,
    user_preferences,
)

urlpatterns = [
    path("auth/csrf/", csrf, name="auth-csrf"),
    path("auth/register/", register, name="auth-register"),
    path("auth/login/", sign_in, name="auth-login"),
    path("auth/logout/", sign_out, name="auth-logout"),
    path("auth/me/", current_user, name="auth-me"),
    path("account/summary/", account_summary, name="account-summary"),
    path("account/profile/", profile_settings, name="account-profile"),
    path("auth/preferences/", user_preferences, name="auth-preferences"),
    path("auth/telegram/challenge/", telegram_challenge, name="auth-telegram-challenge"),
    path("auth/telegram/challenge/complete/", telegram_challenge_complete, name="auth-telegram-complete"),
    path("auth/telegram/webhook/", telegram_webhook, name="auth-telegram-webhook"),
]
