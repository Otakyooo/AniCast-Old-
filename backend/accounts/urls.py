from django.urls import path

from .views import csrf, current_user, register, sign_in, sign_out, telegram_login

urlpatterns = [
    path("auth/csrf/", csrf, name="auth-csrf"),
    path("auth/register/", register, name="auth-register"),
    path("auth/login/", sign_in, name="auth-login"),
    path("auth/logout/", sign_out, name="auth-logout"),
    path("auth/me/", current_user, name="auth-me"),
    path("auth/telegram/login/", telegram_login, name="auth-telegram-login"),
]
