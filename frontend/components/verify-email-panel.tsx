"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { confirmEmailVerification } from "../lib/auth";
import styles from "../app/auth.module.css";
import { useI18n } from "./i18n-provider";

/**
 * Spend a verification link on load.
 *
 * No button: the person already acted by opening the link from their mailbox,
 * and asking them to confirm again would only add a step that can be abandoned.
 * The guard ref keeps React's development double-invoke from spending the
 * single-use token twice and reporting the second, expected failure.
 */
export function VerifyEmailPanel({ token }: { token: string }) {
  const { t } = useI18n();
  const [state, setState] = useState<"pending" | "done" | "failed">(token ? "pending" : "failed");
  const [error, setError] = useState(token ? "" : t("auth.resetNoToken"));
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    confirmEmailVerification(token)
      .then(() => setState("done"))
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : t("auth.verifyFailed"));
        setState("failed");
      });
  }, [token, t]);

  if (state === "pending") return <p className={styles.accountState} role="status">{t("auth.verifyPending")}</p>;

  if (state === "done") {
    return (
      <div className={styles.accountState}>
        <p role="status">{t("auth.verifyDone")}</p>
        <Link className={styles.submit} href="/account">{t("auth.toAccount")}</Link>
        {/* Many people reach this page while locked out: the reset request they
            made is what mailed this link, so the way onward is a fresh reset
            request, not the account page they cannot open yet. */}
        <Link className={styles.secondary} href="/forgot-password">{t("auth.resetRequestNew")}</Link>
      </div>
    );
  }

  return (
    <div className={styles.accountState}>
      <p className={styles.error} role="alert">{error || t("auth.verifyFailed")}</p>
      <Link className={styles.secondary} href="/settings">{t("security.sendVerification")}</Link>
    </div>
  );
}
