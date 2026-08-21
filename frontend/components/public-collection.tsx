"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import styles from "../app/collections/collections.module.css";
import { getPublicCollection, type CollectionDetail } from "../lib/collections";
import { CatalogCard } from "./catalog-card";
import { useI18n } from "./i18n-provider";

export function PublicCollection({ ownerPublicId, slug }: { ownerPublicId: string; slug: string }) {
  const { t } = useI18n();
  const [collection, setCollection] = useState<CollectionDetail>();
  const [error, setError] = useState(false);
  useEffect(() => { const controller = new AbortController(); getPublicCollection(ownerPublicId, slug, controller.signal).then(setCollection).catch((reason) => { if (!(reason instanceof DOMException && reason.name === "AbortError")) setError(true); }); return () => controller.abort(); }, [ownerPublicId, slug]);
  if (!collection && !error) return <div className={styles.empty} role="status">{t("collections.loading")}</div>;
  if (!collection) return <div className={styles.empty}><strong>{t("collections.publicError")}</strong><Link href="/catalog">{t("title.backCatalog")}</Link></div>;
  return <><header className={styles.publicHeader}><p className="eyebrow">{t("collections.publicLabel")}</p><h1>{collection.name}</h1>{collection.description && <p>{collection.description}</p>}<span className="muted">{t("collections.by", { name: collection.owner?.display_name ?? t("collections.owner") })}</span></header>{collection.items.length ? <div className={`catalog-grid ${styles.publicGrid}`}>{collection.items.map((item) => <CatalogCard item={item.title} key={item.title.slug} />)}</div> : <div className={styles.empty}><strong>{t("collections.noTitles")}</strong></div>}</>;
}
