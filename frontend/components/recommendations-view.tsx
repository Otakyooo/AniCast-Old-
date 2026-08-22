"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getRecommendations, type Recommendation } from "../lib/recommendations";
import { CatalogCard } from "./catalog-card";
import { useI18n } from "./i18n-provider";
import styles from "../app/discovery.module.css";

interface RecommendationsState {
  items: Recommendation[];
  nextPage: number | null;
  guest: boolean;
  loading: boolean;
}

export function RecommendationsView() {
  const { t } = useI18n();
  const [state, setState] = useState<RecommendationsState>();

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
  if (state.guest) return <div className="empty-state"><strong>{t("recommendations.guest")}</strong><Link href="/login">{t("common.login")}</Link></div>;
  if (!state.items.length) return <div className="empty-state"><strong>{t("recommendations.empty")}</strong></div>;
  return (
    <>
      <div className="catalog-grid">
        {state.items.map((item) => (
          <div key={item.title.slug}>
            <CatalogCard item={item.title} />
            <span className={styles.score}>{t("recommendations.score", { score: item.score })}</span>
          </div>
        ))}
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
