"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { HistoryApiError, recordEpisodeOpen, setEpisodeWatched, type EpisodeProgress } from "../lib/history";
import styles from "../app/history.module.css";

export function EpisodeProgressControl({ slug, number }: { slug: string; number: number }) {
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
      else setError("Не удалось сохранить открытие эпизода.");
    });
  }, [slug, number]);

  async function toggle() {
    if (!progress) return;
    setPending(true); setError("");
    try { setProgress(await setEpisodeWatched(slug, number, !progress.is_watched)); }
    catch { setError("Не удалось обновить отметку просмотра."); }
    finally { setPending(false); }
  }

  if (guest) return <div className={styles.progress}><span>Войдите, чтобы сохранить эпизод в истории.</span><Link href="/login">Войти</Link></div>;
  return <div className={styles.progress}>{progress ? <><span>{progress.is_watched ? "Эпизод просмотрен" : "Эпизод добавлен в историю"}</span><button type="button" disabled={pending} onClick={toggle}>{progress.is_watched ? "Снять отметку" : "Отметить просмотренным"}</button></> : <span>Сохраняем открытие...</span>}{error && <span className={styles.error} role="alert">{error}</span>}</div>;
}
