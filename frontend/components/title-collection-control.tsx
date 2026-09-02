"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import styles from "../app/collections/collections.module.css";
import { CollectionsApiError, addCollectionItem, deleteCollectionItem, getCollections, type CollectionSummary } from "../lib/collections";
import { useI18n } from "./i18n-provider";

export function TitleCollectionControl({ titleSlug }: { titleSlug: string }) {
  const { t } = useI18n();
  const [collections, setCollections] = useState<CollectionSummary[]>();
  const [included, setIncluded] = useState<Set<string>>(new Set());
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState<string>();
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    // The server answers membership for this one title, so the client no longer
    // needs every collection's full item list to compute it.
    getCollections(controller.signal, titleSlug).then((result) => {
      setCollections(result);
      setIncluded(new Set(result.filter((collection) => collection.contains_title).map((collection) => collection.slug)));
    }).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof CollectionsApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(t("collections.loadError"));
    });
    return () => controller.abort();
  }, [titleSlug, t]);

  async function toggle(slug: string) {
    setPending(slug); setError("");
    try {
      const next = new Set(included);
      if (next.has(slug)) { await deleteCollectionItem(slug, titleSlug); next.delete(slug); }
      else { await addCollectionItem(slug, titleSlug); next.add(slug); }
      setIncluded(next);
    } catch { setError(t("collections.itemError")); }
    finally { setPending(undefined); }
  }

  if (guest) return null;
  if (!collections && !error) return <div className={styles.control} role="status">{t("collections.loading")}</div>;
  return <section className={styles.control}><strong>{t("collections.addTitle")}</strong>{collections?.length ? <div className={styles.controlList}>{collections.map((collection) => <button className={included.has(collection.slug) ? styles.primary : styles.secondary} type="button" disabled={Boolean(pending)} aria-pressed={included.has(collection.slug)} onClick={() => toggle(collection.slug)} key={collection.slug}>{pending === collection.slug ? t("collections.saving") : collection.name}{included.has(collection.slug) ? ` · ${t("collections.added")}` : ""}</button>)}</div> : <Link href="/collections">{t("collections.createFirst")}</Link>}{error && <span className={styles.error} role="alert">{error}</span>}</section>;
}
