"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { MailUnavailableError, requestPasswordReset } from "../lib/auth";
import styles from "../app/auth.module.css";
import { useI18n } from "./i18n-provider";

/**
 * Request a reset link.
 *
 * The success state is reached for any syntactically valid address, including
 * ones with no account: the backend answers identically either way, and showing
 * a different screen here would rebuild the enumeration oracle it avoids.
 */
export function ForgotPasswordForm() {
  const { t } = useI18n();
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const email = String(new FormData(event.currentTarget).get("email") ?? "");
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (reason) {
      setError(
        reason instanceof MailUnavailableError
          ? t("security.mailUnavailable")
          : reason instanceof Error
            ? reason.message
            : t("common.error"),
      );
    } finally {
      setPending(false);
    }
  }

  if (sent) {
    return (
      <div className={styles.accountState}>
        <p role="status">{t("auth.forgotSent")}</p>
        <p className={styles.hint}>{t("auth.forgotSentHint")}</p>
        <Link className={styles.secondary} href="/login">{t("auth.backToLogin")}</Link>
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <label><span>Email</span><input name="email" type="email" autoComplete="email" required /></label>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button className={styles.submit} type="submit" disabled={pending}>
        {pending ? t("auth.wait") : t("auth.forgotSubmit")}
      </button>
      <p className={styles.switch}><Link href="/login">{t("auth.backToLogin")}</Link></p>
    </form>
  );
}
