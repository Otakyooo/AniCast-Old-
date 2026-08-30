"use client";

import Link from "next/link";
import { Play } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import {
  deleteLibraryEntry,
  getLibraryEntry,
  LibraryApiError,
  putLibraryEntry,
  type LibraryEntry,
  type LibraryStatus,
} from "../lib/library";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

interface TitleActionsProps {
  slug: string;
  watchHref?: string;
}

/** Primary playback link plus authenticated library and favorite actions. */
export function TitleActions({ slug, watchHref }: TitleActionsProps) {
  const { t } = useI18n();
  const [entry, setEntry] = useState<LibraryEntry | null | undefined>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setEntry(undefined);
    setGuest(false);
    setError("");

    getLibraryEntry(slug, controller.signal)
      .then(setEntry)
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
        else setError(t("common.error"));
      });

    return () => controller.abort();
  }, [slug, t]);

  async function update(status: LibraryStatus, favorite: boolean) {
    setPending(true);
    setError("");
    try {
      setEntry(await putLibraryEntry(slug, { status, is_favorite: favorite }));
    } catch {
      setError(t("common.error"));
    } finally {
      setPending(false);
    }
  }

  async function remove() {
    setPending(true);
    setError("");
    try {
      await deleteLibraryEntry(slug);
      setEntry(null);
    } catch {
      setError(t("common.error"));
    } finally {
      setPending(false);
    }
  }

  const isFavorite = entry?.is_favorite ?? false;
  const inLibrary = Boolean(entry);

  return (
    <div className={styles.actions}>
      <div className={styles.actionRow}>
        {watchHref && (
          <Link className={styles.watch} href={watchHref}>
            <Play aria-hidden="true" weight="fill" size={18} />
            {t("watch.title")}
          </Link>
        )}
        {guest ? (
          <Link className={styles.secondaryAction} href="/login">{t("common.login")}</Link>
        ) : (
          <>
            <button
              className={inLibrary ? styles.actionActive : styles.secondaryAction}
              type="button"
              disabled={pending || entry === undefined}
              aria-pressed={inLibrary}
              onClick={() => (inLibrary ? remove() : update("watching", false))}
            >
              {inLibrary ? t("title.inLibrary") : t("title.addLibrary")}
            </button>
            <button
              className={isFavorite ? styles.favoriteActive : styles.secondaryAction}
              type="button"
              disabled={pending || entry === undefined}
              aria-pressed={isFavorite}
              onClick={() => update(entry?.status ?? "planned", !isFavorite)}
            >
              <span aria-hidden="true">{isFavorite ? "★" : "☆"}</span>
              {isFavorite ? t("title.favoriteActive") : t("title.favorite")}
            </button>
          </>
        )}
      </div>

      {entry && (
        <label className={styles.statusField}>
          <span>{t("library.myStatus")}</span>
          <select
            value={entry.status}
            disabled={pending}
            onChange={(event) => update(event.target.value as LibraryStatus, entry.is_favorite)}
          >
            <option value="planned">{t("nav.planned")}</option>
            <option value="watching">{t("nav.watching")}</option>
            <option value="completed">{t("nav.completed")}</option>
            <option value="on_hold">{t("library.onHold")}</option>
            <option value="dropped">{t("library.dropped")}</option>
          </select>
        </label>
      )}

      {guest && <p className={styles.actionHint}>{t("title.actionsGuest")}</p>}
      {error && <p className={styles.actionError} role="alert">{error}</p>}
    </div>
  );
}
