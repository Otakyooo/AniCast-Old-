"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { getSessionUser, updatePublicProfile, type SessionUser } from "../lib/auth";
import { useI18n } from "./i18n-provider";
import styles from "../app/settings/settings.module.css";

export function ProfileSettingsPanel() {
  const { t } = useI18n();
  const [user, setUser] = useState<SessionUser | null>();
  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getSessionUser().then((value) => {
      setUser(value);
      if (value) {
        setDisplayName(value.display_name);
        setBio(value.bio);
        setIsPublic(value.profile_is_public);
      }
    }).catch(() => setUser(null));
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage("");
    try {
      const updated = await updatePublicProfile({ display_name: displayName, bio, profile_is_public: isPublic });
      setUser(updated);
      setMessage(t("social.profileSaved"));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t("common.error"));
    } finally {
      setPending(false);
    }
  }

  if (user === undefined) return <section className={styles.panel}>{t("common.loading")}</section>;
  if (user === null) return null;
  const profileHref = `/users/${user.public_id}`;

  return (
    <section className={styles.panel} aria-labelledby="public-profile-settings">
      <div className={styles.heading}>
        <div>
          <p className="eyebrow">{t("social.eyebrow")}</p>
          <h2 id="public-profile-settings">{t("social.settingsTitle")}</h2>
          <p>{t("social.settingsDescription")}</p>
        </div>
        {user.profile_is_public && <Link className={styles.profileLink} href={profileHref}>{t("social.openProfile")} →</Link>}
      </div>
      <form className={styles.form} onSubmit={submit}>
        <label>
          <span>{t("social.displayName")}</span>
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={80} required />
        </label>
        <label>
          <span>{t("social.bio")}</span>
          <textarea value={bio} onChange={(event) => setBio(event.target.value)} maxLength={280} rows={4} placeholder={t("social.bioPlaceholder")} />
          <small>{bio.length}/280</small>
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={isPublic} onChange={(event) => setIsPublic(event.target.checked)} />
          <span><strong>{t("social.publicProfile")}</strong><small>{t("social.publicProfileHint")}</small></span>
        </label>
        <div className={styles.actions}>
          <button type="submit" disabled={pending}>{pending ? t("auth.wait") : t("common.save")}</button>
          {message && <span role="status">{message}</span>}
        </div>
      </form>
    </section>
  );
}
