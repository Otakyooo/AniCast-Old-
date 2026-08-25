"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { CatalogItem } from "../lib/api";
import { getRecommendations } from "../lib/recommendations";
import { CatalogCard } from "./catalog-card";
import { useI18n } from "./i18n-provider";
import styles from "../app/profile.module.css";

/**
 * Top personal recommendations for the account hub. Collapses for guests
 * (the API answers 401/403 and getRecommendations returns null), failures
 * and empty results so the cabinet never shows placeholder blocks.
 */
export function RecommendationShelf() {
  const { t } = useI18n();
  const [items, setItems] = useState<CatalogItem[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getRecommendations(1, controller.signal)
      .then((page) => setItems(page ? page.results.slice(0, 6).map((entry) => entry.title) : []))
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setItems([]);
      });
    return () => controller.abort();
  }, []);

  if (!items || items.length === 0) return null;

  return (
    <section aria-label={t("account.recommendedHeading")}>
      <div className={styles.notesHeading}>
        <h2>{t("account.recommendedHeading")}</h2>
        <Link href="/recommendations">{t("home.showAll")}</Link>
      </div>
      <div className="catalog-grid">
        {items.map((item) => (
          <CatalogCard item={item} key={item.slug} />
        ))}
      </div>
    </section>
  );
}
