"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { cachedSessionUser, getSessionUser, signOut, type SessionUser } from "../lib/auth";
import { useI18n } from "./i18n-provider";
import authStyles from "../app/auth.module.css";
import styles from "../app/profile.module.css";

function initial(user: SessionUser | null) {
  const source = user?.display_name?.trim() || user?.email?.trim() || "";
  return source ? source.charAt(0).toUpperCase() : "?";
}

/**
 * Identity block of the unified profile header (design spec §5.1).
 *
 * Like the header UserMenu, the session-cookie guess decides the first paint
 * and the `/auth/me/` probe confirms the real identity afterwards, so a stale
 * cookie can never render someone else's data.
 */
export function ProfileIdentity({ initialSignedIn }: { initialSignedIn: boolean }) {
  const router = useRouter();
  const { t } = useI18n();
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const cached = cachedSessionUser();
    if (cached !== undefined) setUser(cached);
    getSessionUser()
      .then((value) => setUser(value))
      // A failed probe must not break the profile frame: treat it as a guest.
      .catch(() => setUser(null));
  }, []);

  async function logout() {
    setPending(true);
    try {
      await signOut();
      router.push("/");
      router.refresh();
    } catch {
      // Keep the controls in place so the viewer can retry; session unchanged.
    } finally {
      setPending(false);
    }
  }

  const signedIn = user === undefined ? initialSignedIn : user !== null;

  return (
    <>
      <div className={styles.avatar} aria-hidden="true">
        {signedIn ? initial(user ?? null) : "?"}
      </div>
      <div className={styles.identity}>
        <h1 className={styles.name}>
          {signedIn ? (user?.display_name || t("account.viewer")) : t("profile.guest")}
        </h1>
        <p className={styles.email}>
          {signedIn ? (user?.email || t("account.noEmail")) : t("auth.loginText")}
        </p>
      </div>
      <div className={styles.headerActions}>
        {signedIn ? (
          <>
            <Link className={authStyles.secondary} href="/settings">{t("settings.title")}</Link>
            <button className={authStyles.secondary} type="button" disabled={pending} onClick={logout}>
              {pending ? t("auth.wait") : t("account.logout")}
            </button>
          </>
        ) : (
          <Link className={authStyles.submit} href="/login">{t("common.login")}</Link>
        )}
      </div>
    </>
  );
}
