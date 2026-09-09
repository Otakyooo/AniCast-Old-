"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getHistory, HistoryApiError, type HistoryResponse } from "../lib/history";
import { titleWatchHref } from "../lib/seo";
import styles from "../app/history.module.css";
import { useI18n } from "./i18n-provider";

export function HistoryView() {
  const params = useSearchParams();
  const { locale } = useI18n();
  const [attempt, setAttempt] = useState(0);
  const requested = Number(params.get("page"));
  const page = Number.isSafeInteger(requested) && requested > 0 ? requested : 1;
  return <HistoryResults key={`${page}:${locale}:${attempt}`} page={page} retry={() => setAttempt(value => value + 1)} />;
}

function HistoryResults({ page, retry }: { page: number; retry: () => void }) {
  const { t } = useI18n();
  const [history, setHistory] = useState<HistoryResponse>();
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState(false);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getHistory(20, controller.signal, page).then(data => {
      if (!controller.signal.aborted) setHistory(data);
    }).catch(reason => {
      if (controller.signal.aborted) return;
      if (reason instanceof HistoryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else if (reason instanceof HistoryApiError && reason.status === 404) setMissing(true);
      else setError(true);
    });
    return () => controller.abort();
  }, [page]);

  if (guest) return <div className="empty-state"><strong>{t("history.guest")}</strong><span>{t("history.guestText")}</span><Link className="secondary" href="/login">{t("common.login")}</Link></div>;
  if (missing) return <div className="empty-state" role="status"><strong>{t("common.pageMissing")}</strong><Link className="secondary" href="/history">{t("common.firstPage")}</Link></div>;
  if (error) return <div className="empty-state" role="alert"><strong>{t("history.failed")}</strong><button className="secondary" type="button" onClick={retry}>{t("common.retry")}</button></div>;
  if (!history) return <div className="empty-state" role="status"><strong>{t("history.loading")}</strong></div>;
  if (!history.results.length) return <div className="empty-state"><strong>{t("history.empty")}</strong><span>{t("history.emptyText")}</span><Link className="secondary" href="/catalog">{t("home.openCatalog")}</Link></div>;

  const pageCount = Math.max(1, Math.ceil(history.count / 20));
  return <>
    <div className={styles.historyGrid}>{history.results.map(entry => <Link className={styles.historyCard} href={titleWatchHref(entry.title.slug, entry.episode.number)} key={entry.episode.id}>
      <span className={styles.number}>{t("episode.number", { number: entry.episode.number })}</span>
      <strong>{entry.title.name}</strong><span>{entry.episode.name || t("episode.untitled")}</span>
      <small>{entry.is_watched ? t("history.watched") : t("history.recent")}</small>
    </Link>)}</div>
    {pageCount > 1 && <nav className={styles.pagination} aria-label={t("common.pagination")}>
      {page > 1 && <Link className="secondary" href={page === 2 ? "/history" : `/history?page=${page - 1}`}>{t("common.back")}</Link>}
      <span>{t("catalog.page", { current: page, total: pageCount })}</span>
      {page < pageCount && <Link className="secondary" href={`/history?page=${page + 1}`}>{t("common.next")}</Link>}
    </nav>}
  </>;
}
