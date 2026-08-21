"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import styles from "../app/collections/collections.module.css";
import { deleteCollection, deleteCollectionItem, getCollection, updateCollection, updateCollectionItem, type CollectionDetail } from "../lib/collections";
import { useI18n } from "./i18n-provider";

export function CollectionEditor({ slug }: { slug: string }) {
  const { t } = useI18n();
  const [collection, setCollection] = useState<CollectionDetail>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    getCollection(slug, controller.signal).then(setCollection).catch((reason) => {
      if (!(reason instanceof DOMException && reason.name === "AbortError")) setError(t("collections.loadError"));
    });
    return () => controller.abort();
  }, [slug, t]);

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!collection) return;
    setPending(true); setError("");
    try { setCollection(await updateCollection(slug, { name: collection.name, description: collection.description, is_public: collection.is_public })); }
    catch { setError(t("collections.saveError")); }
    finally { setPending(false); }
  }

  async function removeCollection() {
    if (!confirm(t("collections.deleteConfirm"))) return;
    setPending(true);
    try { await deleteCollection(slug); window.location.assign("/collections"); }
    catch { setPending(false); setError(t("collections.deleteError")); }
  }

  async function removeItem(titleSlug: string) {
    if (!collection) return; setPending(true); setError("");
    try { await deleteCollectionItem(slug, titleSlug); setCollection({ ...collection, items: collection.items.filter((item) => item.title.slug !== titleSlug) }); }
    catch { setError(t("collections.itemError")); }
    finally { setPending(false); }
  }

  async function move(index: number, direction: -1 | 1) {
    if (!collection) return;
    const target = index + direction; if (target < 0 || target >= collection.items.length) return;
    const moved = collection.items[index];
    const items = [...collection.items]; [items[index], items[target]] = [items[target], items[index]];
    setPending(true); setError("");
    try {
      await updateCollectionItem(slug, moved.title.slug, target);
      setCollection({ ...collection, items: items.map((item, position) => ({ ...item, position })) });
    } catch { setError(t("collections.reorderError")); }
    finally { setPending(false); }
  }

  if (!collection && !error) return <div className={styles.empty} role="status">{t("collections.loading")}</div>;
  if (!collection) return <div className={styles.empty}><strong>{error}</strong><Link className={styles.secondary} href="/collections">{t("common.back")}</Link></div>;
  const ownerId = collection.owner?.public_id ?? collection.owner_public_id;
  const sharePath = ownerId ? `/collections/${ownerId}/${collection.slug}` : "";

  return <div className={styles.editor}>
    <form className={`${styles.panel} ${styles.form}`} onSubmit={save}>
      <label>{t("collections.name")}<input value={collection.name} required maxLength={120} onChange={(event) => setCollection({ ...collection, name: event.target.value })} /></label>
      <label>{t("collections.description")}<textarea rows={5} value={collection.description} onChange={(event) => setCollection({ ...collection, description: event.target.value })} /></label>
      <label className={styles.check}><input type="checkbox" checked={collection.is_public} onChange={(event) => setCollection({ ...collection, is_public: event.target.checked })} />{t("collections.visibility")}</label>
      {collection.is_public && sharePath && <div className={styles.share}><span>{t("collections.share")}</span><Link href={sharePath}>{sharePath}</Link></div>}
      <div className={styles.actions}><button className={styles.primary} disabled={pending}>{pending ? t("collections.saving") : t("common.save")}</button><button className={styles.danger} disabled={pending} type="button" onClick={removeCollection}>{t("common.delete")}</button></div>
      {error && <span className={styles.error} role="alert">{error}</span>}
    </form>
    <section><div className="section-heading"><h2>{t("collections.titles")}</h2><span className="muted">{t("collections.itemCount", { count: collection.items.length })}</span></div>
      {collection.items.length ? <div className={styles.items}>{collection.items.map((item, index) => <article className={styles.item} key={item.title.slug}><Link className={styles.itemTitle} href={`/titles/${item.title.slug}`}><span className={styles.initial}>{item.title.name.slice(0, 1)}</span><span><strong>{item.title.name}</strong><small>{item.title.year ?? t("year.unknown")}</small></span></Link><div className={styles.itemActions}><button className={styles.iconButton} disabled={pending || index === 0} onClick={() => move(index, -1)} aria-label={t("collections.moveUp")}>↑</button><button className={styles.iconButton} disabled={pending || index === collection.items.length - 1} onClick={() => move(index, 1)} aria-label={t("collections.moveDown")}>↓</button><button className={styles.danger} disabled={pending} onClick={() => removeItem(item.title.slug)}>{t("collections.remove")}</button></div></article>)}</div> : <div className={styles.empty}><strong>{t("collections.noTitles")}</strong><span>{t("collections.addFromTitle")}</span></div>}
    </section>
  </div>;
}
