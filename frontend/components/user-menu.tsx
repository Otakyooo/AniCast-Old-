"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { getSessionUser, signOut, type SessionUser } from "../lib/auth";
import { LanguageSwitcher } from "./language-switcher";
import { useI18n } from "./i18n-provider";
import styles from "../app/user-menu.module.css";

/** Two initials at most, derived from whatever identity data exists. */
function initials(user: SessionUser) {
  const source = user.display_name?.trim() || user.email?.trim() || "";
  if (!source) return "?";
  const parts = source.split(/[\s@._-]+/).filter(Boolean);
  return (parts.slice(0, 2).map((part) => part[0]).join("") || source[0]).toUpperCase();
}

/**
 * Header identity area. Guests get explicit sign-in/sign-up actions; signed-in
 * viewers get an avatar button opening their personal navigation.
 *
 * `initialSignedIn` is the server's guess from the session cookie. It decides
 * the first paint only, so guests always see a sign-in link without JavaScript
 * and authenticated viewers do not flash a sign-in link. The real session is
 * then confirmed by the `/auth/me/` probe, which also handles an expired cookie.
 */
export function UserMenu({ initialSignedIn }: { initialSignedIn: boolean }) {
  const { t } = useI18n();
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    getSessionUser()
      .then((value) => setUser(value))
      // A failed session probe must not break the header: treat it as a guest.
      .catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function logout() {
    setPending(true);
    try {
      await signOut();
      setUser(null);
      setOpen(false);
      router.push("/");
      router.refresh();
    } catch {
      // Keep the menu open so the viewer can retry; the session is unchanged.
    } finally {
      setPending(false);
    }
  }

  const signedIn = user === undefined ? initialSignedIn : user !== null;

  if (!signedIn) {
    return (
      <div className={styles.actions}>
        <LanguageSwitcher />
        <Link className={styles.register} href="/register">{t("nav.register")}</Link>
        <Link className={`profile ${styles.login}`} href="/login">{t("common.login")}</Link>
      </div>
    );
  }

  return (
    <div className={styles.actions} ref={containerRef}>
      <LanguageSwitcher />
      <div className={styles.menuWrap}>
        <button
          className={styles.avatar}
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          aria-controls={menuId}
          aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
          onClick={() => setOpen((value) => !value)}
        >
          <span aria-hidden="true">{user ? initials(user) : "•"}</span>
        </button>
        {open && (
          <div className={styles.menu} id={menuId} role="menu">
            <div className={styles.identity}>
              <strong>{user?.display_name || t("account.viewer")}</strong>
              {user?.email && <small>{user.email}</small>}
            </div>
            <Link className={styles.item} href="/account" role="menuitem" onClick={() => setOpen(false)}>
              {t("nav.myAccount")}
            </Link>
            {/* Spec §3.3: Профиль, Настройки, Выйти; library quick link allowed. */}
            <Link className={styles.item} href="/library" role="menuitem" onClick={() => setOpen(false)}>
              {t("nav.libraryShort")}
            </Link>
            <Link className={styles.item} href="/settings" role="menuitem" onClick={() => setOpen(false)}>
              {t("settings.title")}
            </Link>
            <button className={styles.logout} type="button" role="menuitem" disabled={pending} onClick={logout}>
              {pending ? t("auth.wait") : t("nav.logout")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
