import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";
import { PageShell } from "../../components/page-shell";
import { apiErrorStatus, emptyPage, getFranchises, type FranchiseResponse } from "../../lib/api";
import { getI18n } from "../../i18n/server";
import { catalogPageExists, franchiseSeoState, NO_INDEX_ROBOTS } from "../../lib/seo";
import discovery from "../discovery.module.css";
import styles from "./franchises.module.css";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 20;

type SearchParams = { page?: string; q?: string };

function readParams(params: SearchParams) {
  const parsed = Number.parseInt(params.page ?? "1", 10);
  return {
    page: Number.isInteger(parsed) && parsed > 0 ? parsed : 1,
    query: params.q?.trim() ?? "",
  };
}

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}): Promise<Metadata> {
  const { t } = await getI18n();
  const { page, query } = readParams(await searchParams);
  // Franchise search is a site-search result page: useful to a visitor, a weak
  // and duplicate landing page for a crawler. Real pagination stays indexable.
  let pageExists = true;
  try {
    const snapshot = await getFranchises(page, query);
    pageExists = catalogPageExists(snapshot.count, page, PAGE_SIZE);
  } catch (error) {
    pageExists = apiErrorStatus(error) !== 404;
  }
  const seo = franchiseSeoState({ query, page }, pageExists);
  return {
    title: t("franchise.title"),
    description: t("meta.franchisesDescription"),
    alternates: { canonical: seo.canonical },
    ...(!seo.index ? { robots: NO_INDEX_ROBOTS } : {}),
  };
}

export default async function FranchisesPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const { page, query } = readParams(await searchParams);
  const data = await getFranchises(page, query).catch((): FranchiseResponse => emptyPage());
  const { t } = await getI18n();
  const pages = Math.max(1, Math.ceil(data.count / PAGE_SIZE));
  const href = (target: number) => {
    const search = new URLSearchParams();
    if (query) search.set("q", query);
    if (target > 1) search.set("page", String(target));
    return search.size ? `/franchises?${search}` : "/franchises";
  };
  return <PageShell active="franchises" heading={{ eyebrow: t("franchise.eyebrow"), title: t("franchise.title"), subtitle: t("franchise.subtitle") }}>
    <form className={discovery.searchRow} action="/franchises" role="search">
      <input name="q" defaultValue={query} aria-label={t("search.franchises")} placeholder={t("search.franchises")} />
      <button type="submit">{t("common.search")}</button>
    </form>
    {data.results.length ? <div className={styles.grid}>{data.results.map((item) => (
      <Link className={styles.card} href={`/franchises/${item.slug}`} key={item.slug}>
        <span className={styles.posters} aria-hidden="true">{item.poster_urls.map((poster, index) => <span key={poster} className={styles.poster}><Image src={poster} alt="" fill sizes="110px" quality={92} referrerPolicy="no-referrer" style={{ zIndex: item.poster_urls.length - index }} /></span>)}</span>
        <span className={styles.cardBody}><span className="eyebrow">{t("franchise.label")}</span><strong>{item.name}</strong><small>{item.year_from ? (item.year_to && item.year_to !== item.year_from ? `${item.year_from}–${item.year_to}` : item.year_from) : ""} · {t("franchise.count", { count: item.title_count })}</small></span>
        <span className={styles.arrow}>→</span>
      </Link>
    ))}</div> : <div className="empty-state" role="status"><strong>{query ? t("catalog.notFound") : t("franchise.empty")}</strong>{query && <Link className="secondary" href="/franchises">{t("catalog.resetFilters")}</Link>}</div>}
    {pages > 1 && <nav className={styles.pagination} aria-label={t("franchise.title")}>{page > 1 && <Link href={href(page - 1)}>{t("common.back")}</Link>}<span>{t("catalog.page", { current: page, total: pages })}</span>{page < pages && <Link href={href(page + 1)}>{t("common.next")}</Link>}</nav>}
  </PageShell>;
}
