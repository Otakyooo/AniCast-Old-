import Link from "next/link";
import type { Metadata } from "next";
import { CatalogCard } from "../../components/catalog-card";
import { CatalogFiltersForm } from "../../components/catalog-filters";
import { RandomTitleButton } from "../../components/random-title-button";
import { PageShell } from "../../components/page-shell";
import {
  emptyPage,
  getCatalog,
  getGenres,
  type CatalogFilters,
  type CatalogItem,
  type CatalogOrdering,
} from "../../lib/api";
import { getI18n } from "../../i18n/server";
import styles from "./catalog.module.css";

export const dynamic = "force-dynamic";

const ORDERINGS: CatalogOrdering[] = ["popular", "recent", "name"];

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}): Promise<Metadata> {
  const { t } = await getI18n();
  const params = await searchParams;
  const requestedPage = Number.parseInt(firstValue(params.page), 10);
  const rawOrdering = firstValue(params.ordering);
  const filters: CatalogFilters = {
    q: firstValue(params.q).trim(),
    type: firstValue(params.type),
    status: firstValue(params.status),
    genre: firstValue(params.genre),
    ordering: ORDERINGS.includes(rawOrdering as CatalogOrdering) ? rawOrdering as CatalogOrdering : undefined,
    page: Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1,
  };
  return {
    title: t("catalog.title"),
    description: t("meta.description"),
    // Self-canonical per active view: paginated and filtered pages keep their
    // own address instead of collapsing onto the bare catalog.
    alternates: { canonical: catalogHref(filters, filters.page ?? 1) },
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
  if (filters.ordering) query.set("ordering", filters.ordering);
  if (page > 1) query.set("page", String(page));
  const suffix = query.toString();
  return suffix ? `/catalog?${suffix}` : "/catalog";
}

export default async function CatalogPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const requestedPage = Number.parseInt(firstValue(params.page), 10);
  const rawOrdering = firstValue(params.ordering);
  const filters: CatalogFilters = {
    q: firstValue(params.q).trim(),
    type: firstValue(params.type),
    status: firstValue(params.status),
    genre: firstValue(params.genre),
    ordering: ORDERINGS.includes(rawOrdering as CatalogOrdering) ? rawOrdering as CatalogOrdering : undefined,
    page: Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1,
  };
  const [catalog, genres] = await Promise.all([
    getCatalog(filters).catch(() => emptyPage<CatalogItem>()),
    getGenres().catch(() => []),
  ]);
  const currentPage = filters.page ?? 1;
  const pageCount = Math.max(1, Math.ceil(catalog.count / 20));
  const hasFilters = Boolean(filters.q || filters.type || filters.status || filters.genre || filters.ordering);
  const { t } = await getI18n();

  return <PageShell active="catalog" heading={{ eyebrow: t("catalog.eyebrow"), title: t("catalog.title"), subtitle: t("catalog.subtitle") }}>
    <CatalogFiltersForm
      values={{
        q: filters.q ?? "",
        type: filters.type ?? "",
        status: filters.status ?? "",
        genre: filters.genre ?? "",
        ordering: filters.ordering,
      }}
      genres={genres}
    />
    {catalog.count > 0 && <RandomTitleButton count={catalog.count} />}
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
