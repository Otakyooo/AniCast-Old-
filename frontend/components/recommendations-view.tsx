"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getRecommendations, type RecommendationResponse } from "../lib/recommendations";
import { CatalogCard } from "./catalog-card";
import { useI18n } from "./i18n-provider";
import styles from "../app/discovery.module.css";

export function RecommendationsView() {
  const { t } = useI18n();
  const [data, setData] = useState<RecommendationResponse | null>();
  useEffect(() => { const controller = new AbortController(); getRecommendations(controller.signal).then(setData).catch(() => setData({ count:0,next:null,previous:null,results:[] })); return () => controller.abort(); }, []);
  if (data === null) return <div className="empty-state"><strong>{t("recommendations.guest")}</strong><Link href="/login">{t("common.login")}</Link></div>;
  if (data === undefined) return <div className="empty-state">{t("common.loading")}</div>;
  if (!data.results.length) return <div className="empty-state"><strong>{t("recommendations.empty")}</strong></div>;
  return <div className="catalog-grid">{data.results.map(item => <div key={item.title.slug}><CatalogCard item={item.title} /><span className={styles.score}>{t("recommendations.score", { score: item.score })}</span></div>)}</div>;
}
