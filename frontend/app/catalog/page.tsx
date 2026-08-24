import Link from "next/link";
import type { Metadata } from "next";
import { CatalogCard } from "../../components/catalog-card";
import { PageShell } from "../../components/page-shell";
import { emptyPage, getCatalog, type CatalogFilters, type CatalogResponse } from "../../lib/api";
import { getI18n } from "../../i18n/server";
import styles from "./catalog.module.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return {
    title: t("catalog.title"),
    description: t("meta.description"),
    alternates: { canonical: "/catalog" },
  };
}

type SearchParams = Record<string, string | string[] | undefined>;

function firstValue(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

function catalogHref(filters: CatalogFilters, page: number) {
  const query = new URLSearchParams();
  if (filters.q) query.set("q", filters.q);
  if (filters.type) query.set("type", filters.type);
  if (filters.status) query.set("status", filters.status);
  if (filters.genre) query.set("genre", filters.genre);
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
    genre: firstValue(params.genre),
    page: Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1,
  };
  const catalog: CatalogResponse = await getCatalog(filters).catch(() => emptyPage());
  const currentPage = filters.page ?? 1;
  const pageCount = Math.max(1, Math.ceil(catalog.count / 20));
  const hasFilters = Boolean(filters.q || filters.type || filters.status || filters.genre);
  const { t } = await getI18n();

  return <PageShell active="catalog" heading={{ eyebrow: t("catalog.eyebrow"), title: t("catalog.title"), subtitle: t("catalog.subtitle") }}>
    <form className={styles.filters} action="/catalog">
      {/* The genre filter is set by links from title pages, so carry it through
          the form instead of silently dropping it on submit. */}
      {filters.genre && <input type="hidden" name="genre" value={filters.genre} />}
      <label className={styles.field}>
        <span>{t("catalog.searchLabel")}</span>
        <input name="q" defaultValue={filters.q} placeholder={t("catalog.searchPlaceholder")} />
      </label>
      <label className={styles.field}>
        <span>{t("catalog.format")}</span>
        <select name="type" defaultValue={filters.type}>
          <option value="">{t("catalog.allFormats")}</option>
          <option value="anime">{t("catalog.series")}</option>
          <option value="movie">{t("catalog.movie")}</option>
          <option value="ova">OVA</option>
          <option value="special">{t("catalog.special")}</option>
        </select>
      </label>
      <label className={styles.field}>
        <span>{t("catalog.status")}</span>
        <select name="status" defaultValue={filters.status}>
          <option value="">{t("catalog.anyStatus")}</option>
          <option value="ongoing">{t("status.ongoing")}</option>
          <option value="finished">{t("status.finished")}</option>
          <option value="planned">{t("status.planned")}</option>
        </select>
      </label>
      <button className={styles.submit} type="submit">{t("catalog.apply")}</button>
      {hasFilters && <Link className={styles.reset} href="/catalog">{t("catalog.reset")}</Link>}
    </form>
    {catalog.results.length ? (
      <div className="catalog-grid">{catalog.results.map(item => <CatalogCard item={item} key={item.slug} />)}</div>
    ) : (
      <div className="empty-state" role="status">
        <strong>{hasFilters ? t("catalog.notFound") : t("catalog.empty")}</strong>
        <span>{hasFilters ? t("catalog.changeFilters") : t("catalog.emptyText")}</span>
        {hasFilters && <Link className="secondary" href="/catalog">{t("catalog.resetFilters")}</Link>}
      </div>
    )}
    {pageCount > 1 && (
      <nav className={styles.pagination}>
        {currentPage > 1 && <Link className={styles.pageLink} href={catalogHref(filters, currentPage - 1)}>{t("common.back")}</Link>}
        <span>{t("catalog.page", { current: currentPage, total: pageCount })}</span>
        {currentPage < pageCount && <Link className={styles.pageLink} href={catalogHref(filters, currentPage + 1)}>{t("common.next")}</Link>}
      </nav>
    )}
  </PageShell>;
}
