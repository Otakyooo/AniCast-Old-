"use client";

import Link from "next/link";
import { CaretDown, Play, Star } from "@phosphor-icons/react";
import { useEffect, useState } from "react";
import {
  deleteLibraryEntry,
  getLibraryEntry,
  LibraryApiError,
  putLibraryEntry,
  type LibraryEntry,
  type LibraryStatus,
} from "../lib/library";
import { getContinueWatching, resumeEpisode } from "../lib/continue-watching";
import { titleWatchHref } from "../lib/seo";
import { useI18n } from "./i18n-provider";
import styles from "../app/titles/title.module.css";

interface TitleActionsProps {
  slug: string;
  watchHref?: string;
  explicitEpisode?: boolean;
}

/** Primary playback link plus the single personal-list system.

 * The list state (watching / planned / completed / on hold / dropped) and the
 * "favorite" flag are one control cluster: the status select owns membership,
 * the star marks "Любимое" inside the same library entry. There is no second
 * competing "add to library" button. */
export function TitleActions(props: TitleActionsProps) {
  const { locale } = useI18n();
  return <TitleActionsContent key={`${props.slug}:${locale}`} {...props} />;
}

const STATUS_OPTIONS: Array<{ value: LibraryStatus; labelKey: string }> = [
  { value: "planned", labelKey: "nav.planned" },
  { value: "watching", labelKey: "nav.watching" },
  { value: "completed", labelKey: "nav.completed" },
  { value: "on_hold", labelKey: "library.onHold" },
  { value: "dropped", labelKey: "library.dropped" },
];

function TitleActionsContent({ slug, watchHref, explicitEpisode = false }: TitleActionsProps) {
  const { t } = useI18n();
  const [entry, setEntry] = useState<LibraryEntry | null | undefined>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [resumeNumber, setResumeNumber] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    getLibraryEntry(slug, controller.signal)
      .then(setEntry)
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
        else setError(t("common.error"));
      });

    return () => controller.abort();
  }, [slug, t]);

  useEffect(() => {
    // The viewer's own resume point overrides the generic "watch" action: the
    // button must offer the next unwatched episode, not episode one. Guests
    // and API failures simply keep the server-provided fallback.
    const controller = new AbortController();
    getContinueWatching(controller.signal)
      .then((entries) => {
        const own = entries?.find((item) => item.title.slug === slug);
        const target = own ? resumeEpisode(own) : null;
        setResumeNumber(target ? target.number : null);
      })
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setResumeNumber(null);
      });
    return () => controller.abort();
  }, [slug]);

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

  /** The select owns list membership: the empty option removes the entry. */
  async function changeStatus(value: string) {
    if (value === "") {
      if (entry) await remove();
      return;
    }
    await update(value as LibraryStatus, entry?.is_favorite ?? false);
  }

  /** The star is part of the same list system: it can create the entry as a
   * favorite even before a watch status was chosen. */
  async function toggleFavorite() {
    if (!entry) {
      await update("planned", true);
      return;
    }
    await update(entry.status, !entry.is_favorite);
  }

  const isFavorite = entry?.is_favorite ?? false;
  // The viewer has real playback history for this title but no library entry:
  // offer to file it under «Смотрю» so the shelf and the counters agree.
  const showWatchlistSuggestion = entry === null && resumeNumber !== null;

  return (
    <div className={styles.actions}>
      <div className={styles.actionRow}>
        {watchHref && (
          <Link className={styles.watch} href={!explicitEpisode && resumeNumber !== null ? titleWatchHref(slug, resumeNumber) : watchHref}>
            <Play aria-hidden="true" weight="fill" size={18} />
            {!explicitEpisode && resumeNumber !== null
              ? t("title.continueEpisode", { number: resumeNumber })
              : t("watch.title")}
          </Link>
        )}
        {!guest && (
          <>
            <label className={styles.listControl}>
              <span>{t("title.listLabel")}</span>
              <span className={styles.listSelect}>
                <select
                  value={entry?.status ?? ""}
                  disabled={pending || entry === undefined}
                  onChange={(event) => void changeStatus(event.target.value)}
                >
                  <option value="">{entry === undefined ? t("common.loading") : t("title.notInList")}</option>
                  {STATUS_OPTIONS.map((option) => (
                    <option value={option.value} key={option.value}>{t(option.labelKey)}</option>
                  ))}
                </select>
                <CaretDown aria-hidden="true" weight="bold" />
              </span>
            </label>
            <button
              className={isFavorite ? `${styles.favoriteToggle} ${styles.favoriteActive}` : styles.favoriteToggle}
              type="button"
              disabled={pending}
              aria-pressed={isFavorite}
              aria-label={isFavorite ? t("title.favoriteActive") : t("library.favorite")}
              title={isFavorite ? t("title.favoriteActive") : t("library.favorite")}
              onClick={() => void toggleFavorite()}
            >
              <Star aria-hidden="true" weight={isFavorite ? "fill" : "regular"} size={18} />
            </button>
          </>
        )}
      </div>

      {showWatchlistSuggestion && (
        <p className={styles.actionHint}>
          <button
            className={styles.actionHintLink}
            type="button"
            disabled={pending}
            onClick={() => void update("watching", false)}
          >
            {t("title.addToWatching")}
          </button>
        </p>
      )}

      {/* A guest saw a sign-in button here and this sentence under it: two
          invitations to the same thing, with the header already offering the
          button. The sentence says why signing in helps, so it stays as the
          hero's only sign-in note; the player reports the same state in its own
          line, where it belongs. */}
      {guest && <p className={styles.actionHint}>{t("title.actionsGuest")}</p>}
      {error && <p className={styles.actionError} role="alert">{error}</p>}
    </div>
  );
}
