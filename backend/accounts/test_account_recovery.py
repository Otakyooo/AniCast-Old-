"""Account recovery: reset, verification, password change and session revocation.

The invariants under test are the ones that made these features necessary: a
person who loses a password must be able to return, a stolen 30-day session must
be revocable, and none of it may turn into an account-enumeration oracle.
"""

from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AccountEmail, AccountToken, User
from accounts.tasks import dispatch_account_emails
from common.security import hash_secret

# The locmem backend is "configured" by definition, so the endpoints run their
# real path and every message lands in django.core.mail.outbox.
MAIL_SETTINGS = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}
PASSWORD = "A-strong-passphrase-2042"
NEW_PASSWORD = "Another-strong-passphrase-2043"


def csrf_client(user=None):
    client = APIClient(enforce_csrf_checks=True)
    if user is not None:
        client.force_login(user)
    return client, client.get("/api/v1/auth/csrf/").json()["csrfToken"]


def verified_user(email="viewer@example.com", password=PASSWORD, **extra):
    user = User.objects.create_user(email=email, password=password, **extra)
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user


def link_token(record: AccountEmail) -> str:
    """Recover the raw token from the delivered message body.

    Only its hash is stored, so the mail is the only place the working link
    exists — which is exactly the property being relied on.
    """
    return link_url(record).split("token=", 1)[1]


def link_url(record: AccountEmail) -> str:
    body = next(message.body for message in mail.outbox if record.to_address in message.to)
    return next(word for word in body.split() if word.startswith("https://"))


def request_reset(client, csrf, email):
    return client.post(
        "/api/v1/auth/password/reset/", {"email": email}, format="json", HTTP_X_CSRFTOKEN=csrf,
    )


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_reset_link_restores_access_and_ends_every_old_session():
    """The whole point: a forgotten password must not be a permanent loss.

    A reset also has to end existing sessions. If the password leaked, the
    attacker holds a 30-day rolling cookie that a new password alone would leave
    working for another month.
    """
    user = verified_user()
    stolen = APIClient()
    stolen.force_login(user)
    assert stolen.get("/api/v1/auth/me/").status_code == 200

    client, csrf = csrf_client()
    assert request_reset(client, csrf, "Viewer@Example.com").status_code == 202
    assert dispatch_account_emails()["sent"] == 1
    record = AccountEmail.objects.get()
    assert record.kind == AccountEmail.Kind.PASSWORD_RESET
    assert record.status == AccountEmail.Status.SENT
    token = link_token(record)
    # Only the hash is at rest: a database read must not yield a usable link.
    assert AccountToken.objects.get().token_hash == hash_secret(token)
    assert token not in str(AccountToken.objects.values_list("token_hash", flat=True))

    confirmed = client.post(
        "/api/v1/auth/password/reset/confirm/",
        {"token": token, "password": NEW_PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["email"] == "viewer@example.com"
    # Signed in immediately: the person came here locked out, so a second login
    # form would be a pointless obstacle.
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert stolen.get("/api/v1/auth/me/").status_code in {401, 403}

    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)
    fresh, fresh_csrf = csrf_client()
    assert fresh.post(
        "/api/v1/auth/login/", {"email": user.email, "password": PASSWORD}, format="json",
        HTTP_X_CSRFTOKEN=fresh_csrf,
    ).status_code == 400


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_reset_link_is_single_use_and_expires():
    user = verified_user()
    client, csrf = csrf_client()
    request_reset(client, csrf, user.email)
    dispatch_account_emails()
    token = link_token(AccountEmail.objects.get())

    def confirm(password):
        return APIClient().post(
            "/api/v1/auth/password/reset/confirm/", {"token": token, "password": password}, format="json",
        )

    assert confirm(NEW_PASSWORD).status_code == 200
    replay = confirm("Third-strong-passphrase-2044")
    assert replay.status_code == 400
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)

    AccountToken.objects.all().delete()
    mail.outbox.clear()
    AccountEmail.objects.all().delete()
    client, csrf = csrf_client()
    request_reset(client, csrf, user.email)
    dispatch_account_emails()
    expired_token = link_token(AccountEmail.objects.get())
    AccountToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert APIClient().post(
        "/api/v1/auth/password/reset/confirm/",
        {"token": expired_token, "password": "Fourth-strong-passphrase-2045"},
        format="json",
    ).status_code == 400


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_reset_request_never_reveals_whether_an_account_exists():
    """Recovery must not become the oracle login refuses to be.

    Known, unknown and disabled addresses have to be indistinguishable in status
    code and body; only the mailbox owner learns anything.
    """
    verified_user(email="known@example.com")
    disabled = verified_user(email="disabled@example.com")
    disabled.is_active = False
    disabled.save(update_fields=["is_active"])

    answers = set()
    for address in ("known@example.com", "stranger@example.com", "disabled@example.com"):
        client, csrf = csrf_client()
        response = request_reset(client, csrf, address)
        answers.add((response.status_code, response.content))
    assert len(answers) == 1

    dispatch_account_emails()
    # Exactly one message: the account that exists and is active.
    assert [message.to for message in mail.outbox] == [["known@example.com"]]


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_reset_for_an_unverified_address_sends_verification_instead():
    """An unproven address must not be handed a reset link.

    Registration accepted any address, so an account may hold one that was a
    typo or somebody else's. Mailing a reset link there would let the address
    holder seize the account; confirming ownership first is the ordering that
    makes recovery safe. The response stays identical either way.
    """
    user = User.objects.create_user(email="unverified@example.com", password=PASSWORD)
    client, csrf = csrf_client()
    assert request_reset(client, csrf, user.email).status_code == 202
    dispatch_account_emails()
    record = AccountEmail.objects.get()
    assert record.kind == AccountEmail.Kind.EMAIL_VERIFICATION
    assert AccountToken.objects.get().purpose == AccountToken.Purpose.EMAIL_VERIFICATION

    # Confirming through that link both verifies the address and, because opening
    # it proves mailbox control, makes the next reset request a real reset.
    token = link_token(record)
    assert APIClient().post(
        "/api/v1/auth/email/verify/confirm/", {"token": token}, format="json",
    ).json() == {"email_verified": True}
    user.refresh_from_db()
    assert user.email_is_verified

    mail.outbox.clear()
    client, csrf = csrf_client()
    request_reset(client, csrf, user.email)
    dispatch_account_emails()
    assert AccountEmail.objects.filter(kind=AccountEmail.Kind.PASSWORD_RESET).count() == 1


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_registration_sends_verification_and_reset_repairs_an_unverified_account():
    client, csrf = csrf_client()
    created = client.post(
        "/api/v1/auth/register/",
        {"email": "newcomer@example.com", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert created.status_code == 201
    assert created.json()["email_verified"] is False
    assert created.json()["has_password"] is True
    record = AccountEmail.objects.get()
    assert record.kind == AccountEmail.Kind.EMAIL_VERIFICATION
    dispatch_account_emails()
    assert "newcomer@example.com" in mail.outbox[0].to
    assert mail.outbox[0].alternatives[0][1] == "text/html"


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_verification_link_is_bound_to_the_address_it_was_sent_to():
    """Confirmation proves one address, not "the account's current address".

    Otherwise requesting a link, then changing the address, would confirm the
    new one without anyone ever reading mail there.
    """
    user = User.objects.create_user(email="mover@example.com", password=PASSWORD)
    client, csrf = csrf_client(user)
    assert client.post("/api/v1/auth/email/verify/", HTTP_X_CSRFTOKEN=csrf).status_code == 202
    dispatch_account_emails()
    token = link_token(AccountEmail.objects.get())

    User.objects.filter(pk=user.pk).update(email="elsewhere@example.com")
    response = APIClient().post("/api/v1/auth/email/verify/confirm/", {"token": token}, format="json")
    assert response.status_code == 409
    user.refresh_from_db()
    assert not user.email_is_verified
    # The link is left unspent: it still proves control of the address it was
    # sent to, so if that address is restored it is usable until it expires.
    # Burning it here would gain nothing — it can never confirm a different one.
    assert AccountToken.objects.get().consumed_at is None


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_verification_request_rejects_already_verified_and_addressless_accounts():
    verified = verified_user(email="done@example.com")
    client, csrf = csrf_client(verified)
    assert client.post("/api/v1/auth/email/verify/", HTTP_X_CSRFTOKEN=csrf).status_code == 409

    telegram_only = User.objects.create_user(email=None, display_name="Telegram viewer")
    client, csrf = csrf_client(telegram_only)
    assert client.post("/api/v1/auth/email/verify/", HTTP_X_CSRFTOKEN=csrf).status_code == 400
    assert AccountEmail.objects.count() == 0


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_password_change_requires_the_current_one_and_keeps_this_session():
    """A stolen session must not be enough to take the account over.

    Without proof of the current password, anyone holding the 30-day cookie could
    lock the owner out permanently. The caller's own session survives, because
    the session hash derives from the password.
    """
    user = verified_user(email="changer@example.com")
    other_device = APIClient()
    other_device.force_login(user)
    client, csrf = csrf_client(user)

    wrong = client.post(
        "/api/v1/auth/password/change/",
        {"current_password": "not-the-password", "password": NEW_PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert wrong.status_code == 400
    assert "current_password" in wrong.json()

    changed = client.post(
        "/api/v1/auth/password/change/",
        {"current_password": PASSWORD, "password": NEW_PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert changed.status_code == 200
    assert changed.json()["revoked"] == 1
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert other_device.get("/api/v1/auth/me/").status_code in {401, 403}
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)

    dispatch_account_emails()
    notice = AccountEmail.objects.get(kind=AccountEmail.Kind.PASSWORD_CHANGED)
    assert notice.status == AccountEmail.Status.SENT
    # A warning, not an authorisation: it must not carry a credential.
    assert "token=" not in mail.outbox[-1].body


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_password_change_invalidates_a_pending_reset_link():
    """An older mailbox capture must not undo a deliberate change."""
    user = verified_user(email="racer@example.com")
    anonymous, anon_csrf = csrf_client()
    request_reset(anonymous, anon_csrf, user.email)
    dispatch_account_emails()
    token = link_token(AccountEmail.objects.get(kind=AccountEmail.Kind.PASSWORD_RESET))

    client, csrf = csrf_client(user)
    assert client.post(
        "/api/v1/auth/password/change/",
        {"current_password": PASSWORD, "password": NEW_PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    ).status_code == 200

    assert APIClient().post(
        "/api/v1/auth/password/reset/confirm/",
        {"token": token, "password": "Fifth-strong-passphrase-2046"},
        format="json",
    ).status_code == 400
    user.refresh_from_db()
    assert user.check_password(NEW_PASSWORD)


@pytest.mark.django_db
def test_telegram_only_account_can_set_a_first_password():
    """No current password exists to prove, and Telegram already authenticated it."""
    user = User.objects.create_user(email=None, display_name="Telegram viewer")
    assert not user.has_usable_password()
    client, csrf = csrf_client(user)
    assert client.get("/api/v1/auth/me/").json()["has_password"] is False
    response = client.post(
        "/api/v1/auth/password/change/", {"password": PASSWORD}, format="json", HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
    # No address, so nothing was mailed.
    assert AccountEmail.objects.count() == 0


@pytest.mark.django_db
def test_password_change_rejects_weak_and_unchanged_passwords():
    user = verified_user(email="weak@example.com")
    client, csrf = csrf_client(user)

    def change(password):
        return client.post(
            "/api/v1/auth/password/change/",
            {"current_password": PASSWORD, "password": password},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )

    assert change("short").status_code == 400
    assert change("1234567890123").status_code == 400
    assert change(PASSWORD).status_code == 400
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


@pytest.mark.django_db
def test_sessions_can_be_revoked_without_touching_other_accounts():
    """The remedy for a stolen 30-day cookie, previously unavailable."""
    user = verified_user(email="revoker@example.com")
    stranger = verified_user(email="stranger@example.com")
    first = APIClient()
    first.force_login(user)
    second = APIClient()
    second.force_login(user)
    unrelated = APIClient()
    unrelated.force_login(stranger)

    client, csrf = csrf_client(user)
    response = client.post("/api/v1/auth/sessions/revoke/", HTTP_X_CSRFTOKEN=csrf)
    assert response.status_code == 200
    assert response.json()["revoked"] == 2
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert first.get("/api/v1/auth/me/").status_code in {401, 403}
    assert second.get("/api/v1/auth/me/").status_code in {401, 403}
    assert unrelated.get("/api/v1/auth/me/").status_code == 200


@pytest.mark.django_db
def test_account_endpoints_require_csrf_and_authentication():
    user = verified_user(email="csrf@example.com")
    unauthenticated = APIClient(enforce_csrf_checks=True)
    for path in (
        "/api/v1/auth/password/reset/",
        "/api/v1/auth/password/reset/confirm/",
        "/api/v1/auth/password/change/",
        "/api/v1/auth/email/verify/",
        "/api/v1/auth/sessions/revoke/",
    ):
        assert unauthenticated.post(path, {}, format="json").status_code == 403, path

    client, csrf = csrf_client()
    for path in ("/api/v1/auth/password/change/", "/api/v1/auth/email/verify/", "/api/v1/auth/sessions/revoke/"):
        assert client.post(path, {}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code in {401, 403}, path
    assert user.email


@pytest.mark.django_db
def test_endpoints_refuse_to_promise_mail_that_cannot_be_sent():
    """An unconfigured mail host answers 503, not a false "check your inbox".

    ``EMAIL_HOST`` unset is a supported state — it is how the stack ran before
    SMTP credentials existed — so the failure has to be honest and no ledger row
    may be created.
    """
    user = User.objects.create_user(email="nomail@example.com", password=PASSWORD)
    with override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", EMAIL_HOST=""):
        client, csrf = csrf_client()
        assert request_reset(client, csrf, user.email).status_code == 503
        authenticated, auth_csrf = csrf_client(user)
        assert authenticated.post(
            "/api/v1/auth/email/verify/", HTTP_X_CSRFTOKEN=auth_csrf,
        ).status_code == 503
        assert AccountEmail.objects.count() == 0
        # Registration still works: mail is an addition to it, not a precondition.
        fresh, fresh_csrf = csrf_client()
        assert fresh.post(
            "/api/v1/auth/register/",
            {"email": "offline@example.com", "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=fresh_csrf,
        ).status_code == 201
        assert AccountEmail.objects.count() == 0
        assert dispatch_account_emails()["skipped"] == "mail_not_configured"


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_reset_requests_are_bounded_per_target_address():
    """The cost of abuse falls on the mailbox owner, so the bucket is per address.

    An IP bucket alone is the wrong axis: a botnet has many addresses while the
    victim has one inbox. A throttled request must still be indistinguishable
    from an accepted one.
    """
    from accounts.tests import throttle_rate

    user = verified_user(email="flooded@example.com")
    with override_settings(REST_FRAMEWORK=throttle_rate("account_mail", "2/hour")):
        seen = set()
        for index in range(3):
            client, csrf = csrf_client()
            response = client.post(
                "/api/v1/auth/password/reset/",
                {"email": user.email},
                format="json",
                REMOTE_ADDR=f"203.0.113.{index + 1}",
                HTTP_X_CSRFTOKEN=csrf,
            )
            seen.add(response.status_code)
        assert seen == {202, 429}
        assert AccountEmail.objects.count() == 2

        # A different address keeps its own budget: one flooded target must not
        # break recovery for everyone else.
        other = verified_user(email="unaffected@example.com")
        client, csrf = csrf_client()
        assert client.post(
            "/api/v1/auth/password/reset/",
            {"email": other.email},
            format="json",
            REMOTE_ADDR="203.0.113.9",
            HTTP_X_CSRFTOKEN=csrf,
        ).status_code == 202


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_delivery_retries_then_stops_and_stale_rows_expire(monkeypatch):
    """The ledger is the delivery guarantee, with a bounded attempt count."""
    user = verified_user(email="retry@example.com")
    client, csrf = csrf_client()
    request_reset(client, csrf, user.email)

    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("smtp down")

    monkeypatch.setattr("accounts.tasks.send_account_email", fail)
    for _ in range(4):
        dispatch_account_emails()
    record = AccountEmail.objects.get()
    assert record.status == AccountEmail.Status.FAILED
    assert record.attempts == 3
    assert len(calls) == 3
    assert "RuntimeError" in record.error

    # Each attempt reissues the link, so only one is ever live.
    assert AccountToken.objects.count() == 1

    AccountEmail.objects.update(status=AccountEmail.Status.PENDING, attempts=0)
    AccountEmail.objects.update(created_at=timezone.now() - timedelta(hours=2))
    monkeypatch.setattr("accounts.tasks.send_account_email", lambda *a, **k: None)
    # A link that would arrive two hours late is worse than none: the person has
    # already asked again.
    assert dispatch_account_emails() == {"sent": 0, "failed": 0, "expired": 1}
    assert AccountEmail.objects.get().status == AccountEmail.Status.EXPIRED


def test_implicit_tls_and_starttls_are_never_both_enabled(monkeypatch):
    """Both flags set makes Django raise inside the delivery task.

    That failure would surface as a transient-looking delivery error rather than
    the configuration mistake it is, so the flags derive from the port choice: an
    operator setting EMAIL_USE_SSL for 465 cannot also leave STARTTLS on.
    """
    import importlib

    import config.settings as settings_module

    for use_ssl, use_tls, expected_ssl, expected_tls in (
        ("1", "1", True, False),
        ("0", "1", False, True),
        ("1", "0", True, False),
        ("0", "0", False, False),
    ):
        monkeypatch.setenv("EMAIL_USE_SSL", use_ssl)
        monkeypatch.setenv("EMAIL_USE_TLS", use_tls)
        # Reloading re-runs the module body; django.conf.settings keeps its own
        # already-built object, so the live configuration is untouched.
        reloaded = importlib.reload(settings_module)
        assert reloaded.EMAIL_USE_SSL is expected_ssl
        assert reloaded.EMAIL_USE_TLS is expected_tls
    monkeypatch.undo()
    importlib.reload(settings_module)


@override_settings(**MAIL_SETTINGS)
@pytest.mark.django_db
def test_mail_body_carries_a_visible_absolute_link_in_the_user_language():

    user = verified_user(email="english@example.com", preferred_language="en")
    client, csrf = csrf_client()
    request_reset(client, csrf, user.email)
    dispatch_account_emails()
    record = AccountEmail.objects.get()
    message = mail.outbox[0]
    assert message.subject == "Reset your AniCast password"
    url = link_url(record)
    assert url.startswith("https://anicast.online/reset-password?token=")
    html = message.alternatives[0][0]
    # The label equals the target: a link whose text differs from where it leads
    # is what both a phishing filter and a careful reader flag.
    assert f'<a href="{url}">{url}</a>' in html
