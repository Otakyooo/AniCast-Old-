"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CatalogCard } from "./catalog-card";
import { CollectionsList } from "./collections-list";
import { getLibrary, LibraryApiError, type LibraryResponse } from "../lib/library";
import styles from "../app/library/library.module.css";
import { useI18n } from "./i18n-provider";

/**
 * The library tab of the profile (design freeze v0.2, acceptance #5): titles
 * with status/favorite filters plus user collections as a sibling view, so
 * lists live inside the library instead of a separate global section.
 */
export function LibraryView() {
  const { t } = useI18n();
  const filters = [[t("library.all"), "/library"], [t("nav.watching"), "/library?status=watching"], [t("nav.planned"), "/library?status=planned"], [t("nav.completed"), "/library?status=completed"], [t("library.onHold"), "/library?status=on_hold"], [t("library.dropped"), "/library?status=dropped"], [t("nav.favorites"), "/library?favorite=true"]];
  const statusLabels: Record<string, string> = { planned: t("nav.planned"), watching: t("nav.watching"), completed: t("nav.completed"), on_hold: t("library.onHold"), dropped: t("library.dropped") };
  const params = useSearchParams();
  const collectionsView = params.get("view") === "collections";
  const [data, setData] = useState<LibraryResponse>();
  const [guest, setGuest] = useState(false);
  const [error, setError] = useState("");
  const status = params.get("status") ?? undefined;
  const favorite = params.get("favorite") === "true";
  const page = Math.max(1, Number(params.get("page")) || 1);

  useEffect(() => {
    if (collectionsView) return;
    const controller = new AbortController();
    setData(undefined); setError(""); setGuest(false);
    getLibrary({ status, favorite, page }, controller.signal).then(setData).catch((reason) => {
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      if (reason instanceof LibraryApiError && [401, 403].includes(reason.status)) setGuest(true);
      else setError(t("common.error"));
    });
    return () => controller.abort();
  }, [status, favorite, page, collectionsView, t]);

  // The current filter is derived from the URL, so the active chip stays
  // correct after a reload or a shared link.
  const activeHref = status ? `/library?status=${status}` : favorite ? "/library?favorite=true" : "/library";

  let titlesBlock: React.ReactNode;
  if (guest) {
    titlesBlock = <div className="empty-state"><strong>{t("common.login")}</strong><span>{t("library.guest")}</span><Link className={styles.primary} href="/login">{t("common.login")}</Link></div>;
  } else if (error) {
    titlesBlock = <div className="empty-state" role="alert"><strong>{error}</strong></div>;
  } else if (!data) {
    titlesBlock = <div className="empty-state" role="status"><strong>{t("common.loading")}</strong></div>;
  } else {
    const filterQuery = status ? `status=${status}` : favorite ? "favorite=true" : "";
    const pageHref = (target: number) => `/library?${filterQuery}${filterQuery ? "&" : ""}page=${target}`;
    const pageCount = Math.max(1, Math.ceil(data.count / 20));
    titlesBlock = <>
      {data.results.length ? <div className={styles.grid}>{data.results.map((entry) => <div className={styles.entry} key={entry.title.slug}><CatalogCard item={entry.title} /><div className={styles.entryMeta}><span>{statusLabels[entry.status]}</span>{entry.is_favorite && <span>{t("nav.favorites")}</span>}</div></div>)}</div> : <div className="empty-state"><strong>{t("library.empty")}</strong><span>{t("library.emptyText")}</span><Link className={styles.primary} href="/catalog">{t("home.openCatalog")}</Link></div>}
      {pageCount > 1 && <div className={styles.pagination}>{page > 1 && <Link href={pageHref(page - 1)}>{t("common.back")}</Link>}<span>{t("catalog.page", { current: page, total: pageCount })}</span>{page < pageCount && <Link href={pageHref(page + 1)}>{t("common.next")}</Link>}</div>}
    </>;
  }

  return <>
    <nav className={styles.viewSwitch} aria-label={t("library.viewSwitch")}>
      <Link className={!collectionsView ? styles.viewActive : undefined} aria-current={!collectionsView ? "page" : undefined} href="/library">{t("library.viewTitles")}</Link>
      <Link className={collectionsView ? styles.viewActive : undefined} aria-current={collectionsView ? "page" : undefined} href="/library?view=collections">{t("library.viewCollections")}</Link>
    </nav>

    {collectionsView ? <CollectionsList /> : <>
      <nav className={styles.filters} aria-label={t("library.filters")}>{filters.map(([label, href]) => <Link className={href === activeHref ? styles.filterActive : undefined} aria-current={href === activeHref ? "page" : undefined} href={href} key={label}>{label}</Link>)}</nav>
      {titlesBlock}
    </>}
  </>;
}
