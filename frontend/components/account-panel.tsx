"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getSessionUser, signOut, type SessionUser } from "../lib/auth";
import { NotificationPanel } from "./notification-panel";
import { useI18n } from "./i18n-provider";
import styles from "../app/auth.module.css";

export function AccountPanel({ notificationBotUsername }: { notificationBotUsername?: string }) {
  const router = useRouter();
  const { t } = useI18n();
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [error, setError] = useState("");

  useEffect(() => {
    getSessionUser().then(setUser).catch((reason) => setError(reason instanceof Error ? reason.message : t("common.error")));
  }, [t]);

  async function logout() {
    setError("");
    try {
      await signOut();
      router.push("/");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("common.error"));
    }
  }

  if (error) return <div className={styles.accountState} role="alert"><p>{error}</p><Link href="/">{t("account.home")}</Link></div>;
  if (user === undefined) return <div className={styles.accountState} role="status">{t("account.loading")}</div>;
  if (user === null) return <div className={styles.accountState}><h2>{t("account.noSession")}</h2><p>{t("account.noSessionText")}</p><Link className={styles.submit} href="/login">{t("common.login")}</Link></div>;

  return <div className={styles.accountState}><p className="eyebrow">{t("account.eyebrow")}</p><h2>{user.display_name || t("account.viewer")}</h2>{user.email && <p className="muted">{user.email}</p>}<p>{t("account.active")}</p><Link className={styles.submit} href="/library">{t("account.openLibrary")}</Link><NotificationPanel botUsername={notificationBotUsername} /><button className={styles.secondary} type="button" onClick={logout}>{t("account.logout")}</button></div>;
}
