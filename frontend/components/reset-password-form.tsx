"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useId, useState } from "react";
import { confirmPasswordReset, setLanguageCookie } from "../lib/auth";
import styles from "../app/auth.module.css";
import { useI18n } from "./i18n-provider";

/**
 * Set a new password from a mailed link.
 *
 * The token comes from the query string and is never displayed or stored: the
 * component holds it for the single request that spends it.
 */
export function ResetPasswordForm({ token }: { token: string }) {
  const router = useRouter();
  const { t } = useI18n();
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const hintId = useId();

  if (!token) {
    return (
      <div className={styles.accountState}>
        <p className={styles.error} role="alert">{t("auth.resetNoToken")}</p>
        <Link className={styles.secondary} href="/forgot-password">{t("auth.resetRequestNew")}</Link>
      </div>
    );
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const password = String(data.get("password") ?? "");
    if (password !== String(data.get("repeat") ?? "")) {
      setError(t("auth.passwordMismatch"));
      return;
    }
    setPending(true);
    setError("");
    try {
      const user = await confirmPasswordReset(token, password);
      setLanguageCookie(user.preferred_language);
      setDone(true);
      // The reset signs the person in, so the server components that render the
      // header and account state have to be re-fetched.
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("common.error"));
    } finally {
      setPending(false);
    }
  }

  if (done) {
    return (
      <div className={styles.accountState}>
        <p role="status">{t("auth.resetDone")}</p>
        <Link className={styles.submit} href="/account">{t("auth.toAccount")}</Link>
      </div>
    );
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <label>
        <span>{t("auth.newPassword")}</span>
        <input name="password" type="password" autoComplete="new-password" minLength={10} required aria-describedby={hintId} />
      </label>
      <label>
        <span>{t("auth.repeatPassword")}</span>
        <input name="repeat" type="password" autoComplete="new-password" minLength={10} required />
      </label>
      <p className={styles.hint} id={hintId}>{t("auth.passwordHint")}</p>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <button className={styles.submit} type="submit" disabled={pending}>
        {pending ? t("auth.wait") : t("auth.resetSubmit")}
      </button>
      <p className={styles.switch}><Link href="/forgot-password">{t("auth.resetRequestNew")}</Link></p>
    </form>
  );
}
