"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getHistory, HistoryApiError, type HistoryResponse } from "../lib/history";
import styles from "../app/history.module.css";
import { useI18n } from "./i18n-provider";

export function HistoryView({ compact = false }: { compact?: boolean }) {
  const { t } = useI18n();
  const [history, setHistory] = useState<HistoryResponse>();
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHistory(compact ? 4 : 20, controller.signal).then(setHistory).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(true);
    });
    return () => controller.abort();
  }, [compact]);

  if (compact && (guest || error || (history && !history.results.length))) return null;
  if (guest) return <div className="empty-state"><strong>{t("history.guest")}</strong><span>{t("history.guestText")}</span><Link href="/login">{t("common.login")}</Link></div>;
  if (error) return <div className="empty-state" role="alert"><strong>{t("history.failed")}</strong></div>;
  if (!history) return <div className="empty-state" role="status"><strong>{t("history.loading")}</strong></div>;
  if (!history.results.length) return <div className="empty-state"><strong>{t("history.empty")}</strong><span>{t("history.emptyText")}</span></div>;

  const content = <div className={styles.historyGrid}>{history.results.map((entry) => <Link className={styles.historyCard} href={`/titles/${entry.title.slug}/episodes/${entry.episode.number}`} key={entry.episode.id}><span className={styles.number}>{t("episode.number", { number: entry.episode.number })}</span><strong>{entry.title.name}</strong><span>{entry.episode.name || t("episode.untitled")}</span><small>{entry.is_watched ? t("history.watched") : t("history.recent")}</small></Link>)}</div>;
  if (!compact) return content;
  return <section className="section"><div className="section-heading"><h2>{t("history.recent")}</h2><Link href="/history">{t("history.all")}</Link></div>{content}</section>;
}
