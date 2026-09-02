"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getCollections, type CollectionSummary } from "../lib/collections";
import { useI18n } from "./i18n-provider";
import styles from "../app/profile.module.css";

/**
 * Up to three personal collections with poster previews for the account hub.
 * Collapses entirely for guests, failures and empty lists so the cabinet
 * never shows placeholder blocks.
 */
export function CollectionPreviews() {
  const { t } = useI18n();
  const [collections, setCollections] = useState<CollectionSummary[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getCollections(controller.signal)
      .then((data) => setCollections(data.slice(0, 3)))
      .catch((reason) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setCollections([]);
      });
    return () => controller.abort();
  }, []);

  if (!collections || collections.length === 0) return null;

  return (
    <section aria-label={t("account.collectionsHeading")}>
      <div className={styles.notesHeading}>
        <h2>{t("account.collectionsHeading")}</h2>
        <Link href="/library?view=collections">{t("home.showAll")}</Link>
      </div>
      <div className={styles.grid}>
        {collections.map((collection) => (
          <Link className={styles.collectionCard} href={`/collections/manage/${collection.slug}`} key={collection.slug}>
            <span className={styles.collectionName}>{collection.name}</span>
            <span className={styles.posterRow}>
              {collection.preview_items.map((item) =>
                item.poster_url ? (
                  <span className={styles.posterThumb} key={item.slug}>
                    <Image className={styles.posterThumbImage} src={item.poster_url} alt="" fill sizes="72px" quality={92} referrerPolicy="no-referrer" />
                  </span>
                ) : (
                  <span className={styles.posterThumb} key={item.slug}>
                    {item.name.slice(0, 1).toUpperCase()}
                  </span>
                ),
              )}
            </span>
            <span className={styles.collectionCount}>{t("collections.itemCount", { count: collection.item_count })}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
