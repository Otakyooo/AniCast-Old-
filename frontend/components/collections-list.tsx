"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";
import styles from "../app/collections/collections.module.css";
import { CollectionsApiError, createCollection, getCollections, type CollectionSummary } from "../lib/collections";
import { useI18n } from "./i18n-provider";

export function CollectionsList() {
  const { t } = useI18n();
  const [collections, setCollections] = useState<CollectionSummary[]>();
  const [guest, setGuest] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const slugHintId = useId();

  useEffect(() => {
    const controller = new AbortController();
    getCollections(controller.signal).then(setCollections).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof CollectionsApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(t("collections.loadError"));
    });
    return () => controller.abort();
  }, [t]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setPending(true); setError("");
    try {
      const created = await createCollection({ name: name.trim(), slug, description: "", is_public: false });
      // The POST answers with the full detail payload; the list renders cards,
      // so the new collection is folded into the card shape it expects.
      setCollections((current) => [
        {
          slug: created.slug,
          name: created.name,
          description: created.description,
          is_public: created.is_public,
          item_count: created.items.length,
          preview_items: [],
          contains_title: null,
          owner: created.owner,
          created_at: created.created_at,
          updated_at: created.updated_at,
        },
        ...(current ?? []),
      ]);
      setName(""); setSlug("");
    } catch { setError(t("collections.saveError")); }
    finally { setPending(false); }
  }

  if (guest) return <div className={styles.empty}><strong>{t("collections.guest")}</strong><Link className={styles.primary} href="/login">{t("common.login")}</Link></div>;
  if (!collections && !error) return <div className={styles.empty} role="status">{t("collections.loading")}</div>;

  return <>
    <form className={`${styles.panel} ${styles.form}`} onSubmit={create}>
      <label>{t("collections.name")}<input value={name} maxLength={120} required onChange={(event) => setName(event.target.value)} placeholder={t("collections.namePlaceholder")} /></label>
      <label>{t("collections.slug")}<input value={slug} maxLength={80} required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" aria-describedby={slugHintId} onChange={(event) => setSlug(event.target.value.toLowerCase())} placeholder={t("collections.slugPlaceholder")} /><small id={slugHintId}>{t("collections.slugHint")}</small></label>
      <div className={styles.actions}><button className={styles.primary} disabled={pending} type="submit">{pending ? t("collections.creating") : t("collections.create")}</button></div>
      {error && <span className={styles.error} role="alert">{error}</span>}
    </form>
    {collections?.length ? <div className={styles.grid}>{collections.map((collection) => <Link className={styles.card} href={`/collections/manage/${collection.slug}`} key={collection.slug}><h2>{collection.name}</h2><p>{collection.description || t("collections.noDescription")}</p><span className={styles.meta}><span>{collection.is_public ? t("collections.public") : t("collections.private")}</span><span>{t("collections.itemCount", { count: collection.item_count })}</span></span></Link>)}</div> : <div className={styles.empty}><strong>{t("collections.empty")}</strong><span>{t("collections.emptyText")}</span></div>}
  </>;
}
