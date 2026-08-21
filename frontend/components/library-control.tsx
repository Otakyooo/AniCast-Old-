"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { deleteLibraryEntry, getLibraryEntry, LibraryApiError, putLibraryEntry, type LibraryEntry, type LibraryStatus } from "../lib/library";
import styles from "../app/library/library.module.css";
import { useI18n } from "./i18n-provider";

export function LibraryControl({ slug }: { slug: string }) {
  const { t } = useI18n();
  const labels: Record<LibraryStatus, string> = { planned: t("nav.planned"), watching: t("nav.watching"), completed: t("nav.completed"), on_hold: t("library.onHold"), dropped: t("library.dropped") };
  const [entry, setEntry] = useState<LibraryEntry | null>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setEntry(undefined);
    setGuest(false);
    setError("");
    getLibraryEntry(slug, controller.signal).then(setEntry).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(t("common.error"));
    });
    return () => controller.abort();
  }, [slug, t]);

  async function update(status: LibraryStatus, favorite: boolean) {
    setPending(true);
    setError("");
    try { setEntry(await putLibraryEntry(slug, { status, is_favorite: favorite })); }
    catch { setError(t("common.error")); }
    finally { setPending(false); }
  }

  async function remove() {
    setPending(true);
    setError("");
    try { await deleteLibraryEntry(slug); setEntry(null); }
    catch { setError(t("common.error")); }
    finally { setPending(false); }
  }

  if (guest) return <div className={styles.control}><p>{t("library.guest")}</p><Link className={styles.primary} href="/login">{t("common.login")}</Link></div>;
  if (entry === undefined) return <div className={styles.control} role="status">{t("common.loading")}</div>;
  if (entry === null) return <div className={styles.control}><p>{t("library.addText")}</p><button className={styles.primary} type="button" disabled={pending} onClick={() => update("planned", false)}>{t("library.add")}</button>{error && <span className={styles.error} role="alert">{error}</span>}</div>;

  return <div className={styles.control}>
    <label><span>{t("library.myStatus")}</span><select value={entry.status} disabled={pending} onChange={(event) => update(event.target.value as LibraryStatus, entry.is_favorite)}>{Object.entries(labels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
    <button className={entry.is_favorite ? styles.favoriteActive : styles.secondary} type="button" disabled={pending} aria-pressed={entry.is_favorite} onClick={() => update(entry.status, !entry.is_favorite)}>{entry.is_favorite ? t("library.favoriteActive") : t("library.favorite")}</button>
    <button className={styles.danger} type="button" disabled={pending} onClick={remove}>{t("common.delete")}</button>
    {error && <span className={styles.error} role="alert">{error}</span>}
  </div>;
}
