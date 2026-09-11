"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { Bell, UserCircle } from "@phosphor-icons/react";
import { getSessionUser, signOut, type SessionUser } from "../lib/auth";
import { LanguageSwitcher } from "./language-switcher";
import { ThemeSwitcher } from "./theme-switcher";
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
 * Header identity area plus preferences. «Моя библиотека» lives in the main
 * navigation now; the user menu carries viewer actions and app preferences
 * (theme and interface language), so the header stays for watching.
 *
 * `initialSignedIn` is the server's guess from the session cookie. It decides
 * the first paint only: guests always see a sign-in link without JavaScript,
 * authenticated viewers do not flash a sign-in link. The real session is then
 * confirmed by the `/auth/me/` probe, which also handles an expired cookie.
 */
export function UserMenu({ initialSignedIn }: { initialSignedIn: boolean }) {
  const { t } = useI18n();
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
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
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
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
        {/* Guests get the same preferences menu as members: theme and
            language are local, not account state. */}
        <PreferencesMenuTrigger />
        <Link className={styles.register} href="/register">{t("nav.register")}</Link>
        <Link className={`profile ${styles.login}`} href="/login">{t("common.login")}</Link>
      </div>
    );
  }

  return (
    <div className={styles.actions} ref={containerRef}>
      <PreferencesMenuTrigger onAfterSelect={undefined} />
      {/* The name keeps the avatar from being an anonymous circle and says
          whose menu the button opens. */}
      {user?.display_name ? <span className={styles.userName}>{user.display_name}</span> : null}
      <div className={styles.menuWrap}>
        <button
          ref={triggerRef}
          className={styles.avatar}
          type="button"
          aria-expanded={open}
          aria-controls={menuId}
          aria-label={open ? t("nav.closeMenu") : t("nav.openMenu")}
          onClick={() => setOpen((value) => !value)}
        >
          <span aria-hidden="true">{user ? initials(user) : "•"}</span>
        </button>
        {open && (
          <div className={styles.menu} id={menuId}>
            <div className={styles.identity}>
              <strong>{user?.display_name || t("account.viewer")}</strong>
              {user?.email && <small>{user.email}</small>}
            </div>
            <Link className={styles.item} href="/account" onClick={() => setOpen(false)}>
              {t("nav.myAccount")}
            </Link>
            {/* Spec §3.3: Профиль, Настройки, Выйти; library and notification
                quick links allowed alongside the required trio. */}
            <Link className={styles.item} href="/library" onClick={() => setOpen(false)}>
              {t("nav.libraryShort")}
            </Link>
            <Link className={styles.item} href="/settings#notifications" onClick={() => setOpen(false)}>
              <Bell aria-hidden="true" size={15} className={styles.itemIcon} />
              {t("nav.notifications")}
            </Link>
            <Link className={styles.item} href="/settings" onClick={() => setOpen(false)}>
              {t("settings.title")}
            </Link>
            {/* Theme and interface language belong to preferences, not the
                main navigation of a watching service. Same controls, one
                row, always available in this menu. */}
            <div className={styles.menuControls}>
              <span className={styles.menuControlsLabel}>{t("theme.label")}</span>
              <ThemeSwitcher />
            </div>
            <div className={styles.menuControls}>
              <span className={styles.menuControlsLabel}>{t("language.label")}</span>
              <LanguageSwitcher />
            </div>
            <button className={styles.logout} type="button" disabled={pending} onClick={logout}>
              {pending ? t("auth.wait") : t("nav.logout")}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** Guest-friendly trigger for the preferences menu: theme + language. On
 * members menu those controls live inside the account dropdown. */
function PreferencesMenuTrigger({ onAfterSelect }: { onAfterSelect?: () => void }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className={styles.menuWrap} ref={containerRef}>
      <button
        ref={triggerRef}
        className={styles.avatar}
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={open ? t("nav.closeMenu") : t("nav.openPrefs")}
        onClick={() => setOpen((value) => !value)}
        title={t("nav.preferences")}
      >
        <UserCircle aria-hidden="true" size={20} weight="bold" />
      </button>
      {open && (
        <div className={styles.menu} id={menuId}>
          <div className={styles.identity}>
            <strong>{t("nav.preferences")}</strong>
          </div>
          <div className={styles.menuControls}>
            <span className={styles.menuControlsLabel}>{t("theme.label")}</span>
            <ThemeSwitcher />
          </div>
          <div className={styles.menuControls}>
            <span className={styles.menuControlsLabel}>{t("language.label")}</span>
            <LanguageSwitcher />
          </div>
        </div>
      )}
    </div>
  );
}
