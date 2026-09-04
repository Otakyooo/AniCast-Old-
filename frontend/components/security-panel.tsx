"use client";

import { FormEvent, useEffect, useId, useState } from "react";
import {
  changePassword,
  getSessionUser,
  MailUnavailableError,
  requestEmailVerification,
  revokeOtherSessions,
  type SessionUser,
} from "../lib/auth";
import { useI18n } from "./i18n-provider";
import styles from "../app/settings/settings.module.css";

/**
 * Password, address confirmation and session revocation.
 *
 * These three belong together because they are the answer to one question: what
 * a person can do when they suspect their account is no longer only theirs.
 */
export function SecurityPanel() {
  const { t } = useI18n();
  const [user, setUser] = useState<SessionUser | null>();
  const [pending, setPending] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [verifyMessage, setVerifyMessage] = useState("");
  const [sessionMessage, setSessionMessage] = useState("");
  const hintId = useId();

  useEffect(() => {
    getSessionUser().then(setUser).catch(() => setUser(null));
  }, []);

  function describe(reason: unknown) {
    if (reason instanceof MailUnavailableError) return t("security.mailUnavailable");
    return reason instanceof Error ? reason.message : t("common.error");
  }

  async function submitPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const password = String(data.get("password") ?? "");
    setPasswordMessage("");
    setPasswordError("");
    if (password !== String(data.get("repeat") ?? "")) {
      setPasswordError(t("auth.passwordMismatch"));
      return;
    }
    setPending(true);
    try {
      const revoked = await changePassword(password, String(data.get("current_password") ?? "") || undefined);
      setPasswordMessage(
        revoked > 0 ? t("security.passwordChangedSessions", { count: revoked }) : t("security.passwordChanged"),
      );
      form.reset();
      // `has_password` flips for a Telegram-only account setting its first one.
      setUser(await getSessionUser());
    } catch (reason) {
      setPasswordError(describe(reason));
    } finally {
      setPending(false);
    }
  }

  async function sendVerification() {
    setPending(true);
    setVerifyMessage("");
    try {
      await requestEmailVerification();
      setVerifyMessage(t("security.verificationSent"));
    } catch (reason) {
      setVerifyMessage(describe(reason));
    } finally {
      setPending(false);
    }
  }

  async function revoke() {
    setPending(true);
    setSessionMessage("");
    try {
      const revoked = await revokeOtherSessions();
      setSessionMessage(revoked > 0 ? t("security.sessionsRevoked", { count: revoked }) : t("security.sessionsNone"));
    } catch (reason) {
      setSessionMessage(describe(reason));
    } finally {
      setPending(false);
    }
  }

  if (user === undefined) return <section className={styles.panel}>{t("common.loading")}</section>;
  if (user === null) return null;

  const settingFirstPassword = !user.has_password;

  return (
    <section className={styles.panel} aria-labelledby="security-settings">
      <div className={styles.heading}>
        <div>
          <p className="eyebrow">{t("settings.title")}</p>
          <h2 id="security-settings">
            {settingFirstPassword ? t("security.setPasswordTitle") : t("security.title")}
          </h2>
          <p>{settingFirstPassword ? t("security.setPasswordDescription") : t("security.description")}</p>
        </div>
      </div>

      {user.email ? (
        <div className={styles.toggle}>
          <span>
            <strong>{user.email_verified ? t("security.emailVerified") : t("security.emailUnverified")}</strong>
            <small>{user.email_verified ? user.email : t("security.emailUnverifiedHint")}</small>
          </span>
          {!user.email_verified && (
            <button type="button" onClick={sendVerification} disabled={pending}>
              {pending ? t("auth.wait") : t("security.sendVerification")}
            </button>
          )}
        </div>
      ) : (
        <p className="muted">{t("security.noEmail")}</p>
      )}
      {verifyMessage && <p role="status">{verifyMessage}</p>}

      <form className={styles.form} onSubmit={submitPassword}>
        {!settingFirstPassword && (
          <label>
            <span>{t("security.currentPassword")}</span>
            <input name="current_password" type="password" autoComplete="current-password" required />
          </label>
        )}
        <label>
          <span>{t("auth.newPassword")}</span>
          <input name="password" type="password" autoComplete="new-password" minLength={10} required aria-describedby={hintId} />
        </label>
        <label>
          <span>{t("auth.repeatPassword")}</span>
          <input name="repeat" type="password" autoComplete="new-password" minLength={10} required />
        </label>
        <small id={hintId} className="muted">{t("auth.passwordHint")}</small>
        {passwordError && <p role="alert">{passwordError}</p>}
        <div className={styles.actions}>
          <button type="submit" disabled={pending}>
            {pending ? t("auth.wait") : settingFirstPassword ? t("security.setPassword") : t("security.changePassword")}
          </button>
          {passwordMessage && <span role="status">{passwordMessage}</span>}
        </div>
      </form>

      <div>
        <h3>{t("security.sessionsTitle")}</h3>
        <p className="muted">{t("security.sessionsDescription")}</p>
        <div className={styles.actions}>
          <button type="button" onClick={revoke} disabled={pending}>
            {pending ? t("auth.wait") : t("security.revokeSessions")}
          </button>
          {sessionMessage && <span role="status">{sessionMessage}</span>}
        </div>
      </div>
    </section>
  );
}
