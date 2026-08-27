"use client";

import styles from "../app/collections/collections.module.css";
import type { CollectionDetail } from "../lib/collections";
import { CatalogCard } from "./catalog-card";
import { useI18n } from "./i18n-provider";

export function PublicCollection({ collection }: { collection: CollectionDetail }) {
  const { t } = useI18n();
  return <><header className={styles.publicHeader}><p className="eyebrow">{t("collections.publicLabel")}</p><h1>{collection.name}</h1>{collection.description && <p>{collection.description}</p>}<span className="muted">{t("collections.by", { name: collection.owner?.display_name ?? t("collections.owner") })}</span></header>{collection.items.length ? <div className={`catalog-grid ${styles.publicGrid}`}>{collection.items.map((item) => <CatalogCard item={item.title} key={item.title.slug} />)}</div> : <div className={styles.empty}><strong>{t("collections.noTitles")}</strong></div>}</>;
}
