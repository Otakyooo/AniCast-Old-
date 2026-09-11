import Link from "next/link";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CatalogCard } from "../../components/catalog-card";
import { CatalogFiltersForm } from "../../components/catalog-filters";
import { RandomTitleButton } from "../../components/random-title-button";
import { PageShell } from "../../components/page-shell";
import { SectionUnavailable } from "../../components/section-unavailable";
import {
  apiErrorStatus,
  getCatalog,
  getGenres,
  type CatalogFilters,
  type CatalogOrdering,
} from "../../lib/api";
import { getI18n } from "../../i18n/server";
import { catalogPageExists, catalogSeoState, NO_INDEX_ROBOTS } from "../../lib/seo";
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
  const rawSeasons = firstValue(params.seasons);
  const filters: CatalogFilters = {
    q: firstValue(params.q).trim(),
    type: firstValue(params.type),
    status: firstValue(params.status),
    genre: firstValue(params.genre),
    ordering: ORDERINGS.includes(rawOrdering as CatalogOrdering) ? rawOrdering as CatalogOrdering : undefined,
    seasons: rawSeasons === "separate" ? "separate" : undefined,
    page: Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1,
  };
  let pageExists = true;
  try {
    const pageSnapshot = await getCatalog(filters);
    pageExists = catalogPageExists(pageSnapshot.count, filters.page ?? 1);
  } catch (error) {
    // DRF answers 404 for a page beyond the paginator range. Preserve that
    // knowledge in metadata even though Next may already have started a
    // streamed response by the time the page component renders notFound().
    pageExists = apiErrorStatus(error) !== 404;
  }
  const seo = catalogSeoState(filters, pageExists);
  return {
    title: t("catalog.title"),
    description: t("meta.catalogDescription"),
    alternates: { canonical: seo.canonical },
    ...(!seo.index ? { robots: NO_INDEX_ROBOTS } : {}),
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
  if (filters.seasons && filters.seasons !== "grouped") query.set("seasons", filters.seasons);
  if (page > 1) query.set("page", String(page));
  const suffix = query.toString();
  return suffix ? `/catalog?${suffix}` : "/catalog";
}

/** The last visible page worth of named links around the current one —
 * windowed so a 40-page catalogue never renders forty numbers. */
function paginationWindow(currentPage: number, pageCount: number): number[] {
  const windowRadius = 2;
  const from = Math.max(1, currentPage - windowRadius);
  const to = Math.min(pageCount, currentPage + windowRadius);
  const pages = new Set<number>([1, pageCount]);
  for (let page = from; page <= to; page += 1) pages.add(page);
  return [...pages].sort((a, b) => a - b);
}

function CatalogPagination({
  currentPage,
  pageCount,
  filters,
  t,
}: {
  currentPage: number;
  pageCount: number;
  filters: CatalogFilters;
  t: (key: string, values?: Record<string, string | number>) => string;
}) {
  const pages = paginationWindow(currentPage, pageCount);
  return (
    <nav className={styles.pagination} aria-label={t("common.pagination")}>
      {currentPage > 1 ? (
        <Link className={styles.pageLink} href={catalogHref(filters, currentPage - 1)}>{t("common.back")}</Link>
      ) : (
        <span className={styles.pageDisabled} aria-hidden="true">{t("common.back")}</span>
      )}
      {pages.flatMap((page, index) => {
        const previous = pages[index - 1];
        const gap = previous !== undefined && page - previous > 1;
        const link = page === currentPage ? (
          <span className={`${styles.pageLink} ${styles.pageLinkCurrent}`} aria-current="page" key={page}>
            {page}
          </span>
        ) : (
          <Link className={styles.pageLink} href={catalogHref(filters, page)} key={page}>
            {page}
          </Link>
        );
        return gap ? [(
          <span className={styles.pageGap} aria-hidden="true" key={`gap-${previous}-${page}`}>…</span>
        ), link] : [link];
      })}
      {currentPage < pageCount ? (
        <Link className={styles.pageLink} href={catalogHref(filters, currentPage + 1)}>{t("common.next")}</Link>
      ) : (
        <span className={styles.pageDisabled} aria-hidden="true">{t("common.next")}</span>
      )}
    </nav>
  );
}

export default async function CatalogPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const requestedPage = Number.parseInt(firstValue(params.page), 10);
  const rawOrdering = firstValue(params.ordering);
  const rawSeasons = firstValue(params.seasons);
  const filters: CatalogFilters = {
    q: firstValue(params.q).trim(),
    type: firstValue(params.type),
    status: firstValue(params.status),
    genre: firstValue(params.genre),
    ordering: ORDERINGS.includes(rawOrdering as CatalogOrdering) ? rawOrdering as CatalogOrdering : undefined,
    seasons: rawSeasons === "separate" ? "separate" : undefined,
    page: Number.isInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1,
  };
  const [catalog, genres] = await Promise.all([
    getCatalog(filters).catch((error) => {
      if (apiErrorStatus(error) === 404) notFound();
      return null;
    }),
    getGenres().catch(() => []),
  ]);
  const currentPage = filters.page ?? 1;
  const pageCount = catalog ? Math.max(1, Math.ceil(catalog.count / 20)) : 1;
  if (catalog && currentPage > pageCount) notFound();
  const hasFilters = Boolean(filters.q || filters.type || filters.status || filters.genre || filters.ordering);
  const { t } = await getI18n();

  // Compact heading: no eyebrow, no marketing subtitle — the filters and the
  // grid are the page. The heading still owns the <h1> landmark.
  return <PageShell active="catalog" heading={{ title: t("catalog.title") }}>
    <CatalogFiltersForm
      key={JSON.stringify(filters)}
      values={{
        q: filters.q ?? "",
        type: filters.type ?? "",
        status: filters.status ?? "",
        genre: filters.genre ?? "",
        ordering: filters.ordering,
      }}
      genres={genres}
    />
    {catalog && catalog.count > 0 && (
      <div className={styles.toolbar}>
        <p className={styles.resultCount}>{t("catalog.found", { count: catalog.count })}</p>
        <Link
          className={styles.seasonsToggle}
          href={catalogHref({ ...filters, seasons: filters.seasons === "separate" ? undefined : "separate" }, 1)}
        >
          {filters.seasons === "separate" ? t("catalog.seasonsGrouped") : t("catalog.seasonsSeparate")}
        </Link>
        <RandomTitleButton key={JSON.stringify(filters)} count={catalog.count} filters={filters} />
      </div>
    )}
    {!catalog ? <SectionUnavailable /> : catalog.results.length ? (
      <div className="catalog-grid">{catalog.results.map(item => <CatalogCard item={item} key={item.slug} />)}</div>
    ) : (
      <div className="empty-state" role="status">
        <strong>{hasFilters ? t("catalog.notFound") : t("catalog.empty")}</strong>
        <span>{hasFilters ? t("catalog.changeFilters") : t("catalog.emptyText")}</span>
        {hasFilters && <Link className="secondary" href="/catalog">{t("catalog.resetFilters")}</Link>}
      </div>
    )}
    {pageCount > 1 && (
      <CatalogPagination currentPage={currentPage} pageCount={pageCount} filters={filters} t={t} />
    )}
  </PageShell>;
}
