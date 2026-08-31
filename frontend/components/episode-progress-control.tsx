"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  getEpisodeProgress,
  HistoryApiError,
  recordEpisodeOpen,
  setEpisodeWatched,
  type EpisodeProgress,
} from "../lib/history";
import styles from "../app/history.module.css";
import { useI18n } from "./i18n-provider";

export function EpisodeProgressControl({
  slug,
  number,
  compact = false,
  recordOnMount = true,
  singlePlayback = false,
  className = "",
}: {
  slug: string;
  number: number;
  compact?: boolean;
  recordOnMount?: boolean;
  singlePlayback?: boolean;
  className?: string;
}) {
  const { t } = useI18n();
  const episodeKey = `${slug}:${number}`;
  const activeEpisodeRef = useRef(episodeKey);
  activeEpisodeRef.current = episodeKey;
  const [progress, setProgress] = useState<EpisodeProgress | null>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [loadFailed, setLoadFailed] = useState(false);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    setProgress(undefined);
    setGuest(false);
    setPending(false);
    setError("");
    setLoadFailed(false);
    const request = recordOnMount
      ? recordEpisodeOpen(slug, number)
      : getEpisodeProgress(slug, number, controller.signal);
    request.then((value) => {
      if (active) setProgress(value);
    }).catch((reason) => {
      if (!active) return;
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else if (!recordOnMount && reason instanceof HistoryApiError && reason.status === 404) setProgress(null);
      else {
        setLoadFailed(true);
        setError(t("common.error"));
      }
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, [slug, number, recordOnMount, reloadVersion, t]);

  async function toggle() {
    if (progress === undefined) return;
    const mutationEpisodeKey = episodeKey;
    setPending(true); setError("");
    try {
      const value = await setEpisodeWatched(slug, number, progress ? !progress.is_watched : true);
      if (activeEpisodeRef.current === mutationEpisodeKey) setProgress(value);
    } catch {
      if (activeEpisodeRef.current === mutationEpisodeKey) setError(t("common.error"));
    } finally {
      if (activeEpisodeRef.current === mutationEpisodeKey) setPending(false);
    }
  }

  const classes = `${styles.progress} ${compact ? styles.progressCompact : ""} ${className}`;
  if (guest && !recordOnMount) return null;
  if (guest) return <div className={classes}><span>{t("history.guestText")}</span><Link href="/login">{t("common.login")}</Link></div>;
  return <div className={classes}>
    {loadFailed ? (
      <button type="button" onClick={() => setReloadVersion((value) => value + 1)}>
        {t("common.retry")}
      </button>
    ) : progress === undefined ? (
      <span>{recordOnMount ? t("episode.saving") : t("common.loading")}</span>
    ) : progress ? (
      <>
        <span>{progress.is_watched
          ? t(singlePlayback ? "watch.progressWatched" : "episode.watched")
          : t(singlePlayback ? "watch.progressInHistory" : "episode.inHistory")}</span>
        <button type="button" disabled={pending} onClick={toggle}>
          {progress.is_watched ? t("episode.unmark") : t("episode.mark")}
        </button>
      </>
    ) : (
      <button type="button" disabled={pending} onClick={toggle}>{t("episode.mark")}</button>
    )}
    {error && <span className={styles.error} role="alert">{error}</span>}
  </div>;
}
