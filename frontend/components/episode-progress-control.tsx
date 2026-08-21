"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { HistoryApiError, recordEpisodeOpen, setEpisodeWatched, type EpisodeProgress } from "../lib/history";
import styles from "../app/history.module.css";
import { useI18n } from "./i18n-provider";

export function EpisodeProgressControl({ slug, number }: { slug: string; number: number }) {
  const { t } = useI18n();
  const recorded = useRef("");
  const [progress, setProgress] = useState<EpisodeProgress>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const episodeKey = `${slug}:${number}`;
    if (recorded.current === episodeKey) return;
    recorded.current = episodeKey;
    recordEpisodeOpen(slug, number).then(setProgress).catch((reason) => {
      if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(t("common.error"));
    });
  }, [slug, number, t]);

  async function toggle() {
    if (!progress) return;
    setPending(true); setError("");
    try { setProgress(await setEpisodeWatched(slug, number, !progress.is_watched)); }
    catch { setError(t("common.error")); }
    finally { setPending(false); }
  }

  if (guest) return <div className={styles.progress}><span>{t("history.guestText")}</span><Link href="/login">{t("common.login")}</Link></div>;
  return <div className={styles.progress}>{progress ? <><span>{progress.is_watched ? t("episode.watched") : t("episode.inHistory")}</span><button type="button" disabled={pending} onClick={toggle}>{progress.is_watched ? t("episode.unmark") : t("episode.mark")}</button></> : <span>{t("episode.saving")}</span>}{error && <span className={styles.error} role="alert">{error}</span>}</div>;
}
