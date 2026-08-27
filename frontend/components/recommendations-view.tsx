"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  dismissRecommendation,
  getRecommendations,
  undismissRecommendation,
  type Recommendation,
} from "../lib/recommendations";
import { recommendationReasonText } from "../lib/recommendation-reasons";
import { CatalogCard } from "./catalog-card";
import { useI18n } from "./i18n-provider";
import styles from "../app/discovery.module.css";

interface RecommendationsState {
  items: Recommendation[];
  nextPage: number | null;
  guest: boolean;
  loading: boolean;
}

interface NoticeState {
  kind: "dismissed" | "error";
  item: Recommendation;
  index: number;
}

const NOTICE_TIMEOUT_MS = 6000;

export function RecommendationsView() {
  const { t } = useI18n();
  const [state, setState] = useState<RecommendationsState>();
  const [notice, setNotice] = useState<NoticeState | null>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getRecommendations(1, controller.signal)
      .then((data) =>
        setState(
          data === null
            ? { items: [], nextPage: null, guest: true, loading: false }
            : { items: data.results, nextPage: data.next ? 2 : null, guest: false, loading: false },
        ),
      )
      .catch(() => setState({ items: [], nextPage: null, guest: false, loading: false }));
    return () => controller.abort();
  }, []);

  useEffect(
    () => () => {
      if (noticeTimer.current) clearTimeout(noticeTimer.current);
    },
    [],
  );

  const scheduleNoticeClear = useCallback(() => {
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(null), NOTICE_TIMEOUT_MS);
  }, []);

  const handleDismiss = useCallback(
    async (item: Recommendation, index: number) => {
      const outcome = await dismissRecommendation(item.title.slug);
      if (outcome === null) return; // the session ended; the next reload shows the guest state
      if (!outcome) {
        setNotice({ kind: "error", item, index });
        scheduleNoticeClear();
        return;
      }
      setState((current) =>
        current
          ? { ...current, items: current.items.filter((entry) => entry.title.slug !== item.title.slug) }
          : current,
      );
      setNotice({ kind: "dismissed", item, index });
      scheduleNoticeClear();
    },
    [scheduleNoticeClear],
  );

  const handleUndo = useCallback(async () => {
    if (!notice || notice.kind !== "dismissed") return;
    const { item, index } = notice;
    setNotice(null);
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    const outcome = await undismissRecommendation(item.title.slug);
    if (!outcome) return; // nothing to restore server-side or the request failed
    setState((current) => {
      if (!current || current.items.some((entry) => entry.title.slug === item.title.slug)) return current;
      const items = [...current.items];
      items.splice(Math.min(index, items.length), 0, item);
      return { ...current, items };
    });
  }, [notice]);

  const loadMore = useCallback(async () => {
    if (!state?.nextPage || state.loading) return;
    setState({ ...state, loading: true });
    try {
      const data = await getRecommendations(state.nextPage);
      if (!data) {
        setState({ ...state, loading: false, nextPage: null });
        return;
      }
      setState({
        items: [...state.items, ...data.results],
        nextPage: data.next ? state.nextPage + 1 : null,
        guest: false,
        loading: false,
      });
    } catch {
      setState({ ...state, loading: false });
    }
  }, [state]);

  if (state === undefined) return <div className="empty-state">{t("common.loading")}</div>;
  if (state.guest)
    return (
      <div className="empty-state">
        <strong>{t("recommendations.guest")}</strong>
        <Link href="/login">{t("common.login")}</Link>
      </div>
    );
  if (!state.items.length) return <div className="empty-state"><strong>{t("recommendations.empty")}</strong></div>;

  return (
    <>
      {notice && (
        <div className={styles.notice} role="status">
          {notice.kind === "dismissed" ? (
            <>
              <span>
                {t("recommendations.dismissed", { name: notice.item.title.name })}
              </span>
              <button type="button" onClick={handleUndo}>
                {t("recommendations.undo")}
              </button>
            </>
          ) : (
            <span>{t("recommendations.dismissFailed")}</span>
          )}
        </div>
      )}
      <div className="catalog-grid">
        {state.items.map((item, index) => {
          const reason = recommendationReasonText(item.reasons, t);
          return (
            <div key={item.title.slug}>
              <CatalogCard item={item.title} />
              <div className={styles.cardMeta}>
                {reason && <span className={styles.reason}>{reason}</span>}
                <button
                  className={styles.dismiss}
                  type="button"
                  title={t("recommendations.dismiss")}
                  aria-label={t("recommendations.dismiss")}
                  onClick={() => handleDismiss(item, index)}
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {state.nextPage && (
        <div className={styles.loadMore}>
          <button className="secondary" type="button" onClick={loadMore} disabled={state.loading}>
            {state.loading ? t("common.loading") : t("recommendations.loadMore")}
          </button>
        </div>
      )}
    </>
  );
}
