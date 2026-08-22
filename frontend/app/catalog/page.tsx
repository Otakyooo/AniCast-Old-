import Link from "next/link";
import { AccountLink } from "../../components/account-link";
import { CatalogCard } from "../../components/catalog-card";
import { Sidebar } from "../../components/sidebar";
import { emptyPage, getCatalog, type CatalogFilters, type CatalogResponse } from "../../lib/api";
import { getI18n } from "../../i18n/server";
import styles from "./catalog.module.css";

export const dynamic = "force-dynamic";

type SearchParams = Record<string, string | string[] | undefined>;

function firstValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function catalogHref(filters: CatalogFilters, page: number) {
  const query = new URLSearchParams();
  if (filters.q) query.set("q", filters.q);
  if (filters.type) query.set("type", filters.type);
  if (filters.status) query.set("status", filters.status);
  if (page > 1) query.set("page", String(page));
  const suffix = query.toString();
  return suffix ? `/catalog?${suffix}` : "/catalog";
}

export default async function CatalogPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const requestedPage = Number.parseInt(firstValue(params.page), 10);
  const filters: CatalogFilters = {
    q: firstValue(params.q).trim(),
    type: firstValue(params.type),
    status: firstValue(params.status),
    page: Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1,
  };
  const catalog: CatalogResponse = await getCatalog(filters).catch(() => emptyPage());
  const currentPage = filters.page ?? 1;
  const pageCount = Math.max(1, Math.ceil(catalog.count / 20));
  const hasFilters = Boolean(filters.q || filters.type || filters.status);
  const { t } = await getI18n();

  return <main className="shell">
    <Sidebar active="catalog" />
    <section className="content"><header className="topbar"><form className="search" action="/catalog"><span aria-hidden="true">⌕</span><input name="q" defaultValue={filters.q} aria-label={t("catalog.searchLabel")} placeholder={t("catalog.searchPlaceholder")} />{filters.type && <input type="hidden" name="type" value={filters.type} />}{filters.status && <input type="hidden" name="status" value={filters.status} />}<button type="submit" className="search-submit">{t("common.search")}</button></form><AccountLink /></header>
      <div className="page-heading"><p className="eyebrow">{t("catalog.eyebrow")}</p><h1>{t("catalog.title")}</h1><p className="muted">{t("catalog.subtitle")}</p></div>
      <form className={styles.filters} action="/catalog">
        {filters.q && <input type="hidden" name="q" value={filters.q} />}
        <label className={styles.field}><span>{t("catalog.format")}</span><select name="type" defaultValue={filters.type}><option value="">{t("catalog.allFormats")}</option><option value="anime">{t("catalog.series")}</option><option value="movie">{t("catalog.movie")}</option><option value="ova">OVA</option><option value="special">{t("catalog.special")}</option></select></label>
        <label className={styles.field}><span>{t("catalog.status")}</span><select name="status" defaultValue={filters.status}><option value="">{t("catalog.anyStatus")}</option><option value="ongoing">{t("status.ongoing")}</option><option value="finished">{t("status.finished")}</option><option value="planned">{t("status.planned")}</option></select></label>
        <button className={styles.submit} type="submit">{t("catalog.apply")}</button>
        {hasFilters && <Link className={styles.reset} href="/catalog">{t("catalog.reset")}</Link>}
      </form>
      {catalog.results.length ? <div className="catalog-grid">{catalog.results.map(item => <CatalogCard item={item} key={item.slug} />)}</div> : <div className="empty-state" role="status"><strong>{hasFilters ? t("catalog.notFound") : t("catalog.empty")}</strong><span>{hasFilters ? t("catalog.changeFilters") : t("catalog.emptyText")}</span>{hasFilters && <Link className="secondary" href="/catalog">{t("catalog.resetFilters")}</Link>}</div>}
      {pageCount > 1 && <nav className={styles.pagination}>{currentPage > 1 && <Link className={styles.pageLink} href={catalogHref(filters, currentPage - 1)}>{t("common.back")}</Link>}<span>{t("catalog.page", { current: currentPage, total: pageCount })}</span>{currentPage < pageCount && <Link className={styles.pageLink} href={catalogHref(filters, currentPage + 1)}>{t("common.next")}</Link>}</nav>}
    </section>
  </main>;
}
