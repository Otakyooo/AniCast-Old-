import Link from "next/link";
import { PageShell } from "../../components/page-shell";
import { emptyPage, getFranchises, type FranchiseResponse } from "../../lib/api";
import { getI18n } from "../../i18n/server";
import discovery from "../discovery.module.css";
import styles from "./franchises.module.css";

export const dynamic = "force-dynamic";

export default async function FranchisesPage({
  searchParams,
}: { searchParams: Promise<{ page?: string; q?: string }> }) {
  const params = await searchParams;
  const rawPage = Number.parseInt(params.page ?? "1", 10);
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const query = params.q?.trim() ?? "";
  const data = await getFranchises(page, query).catch((): FranchiseResponse => emptyPage());
  const { t } = await getI18n();
  const pages = Math.max(1, Math.ceil(data.count / 20));
  const pageHref = (target: number) => {
    const search = new URLSearchParams();
    if (query) search.set("q", query);
    if (target > 1) search.set("page", String(target));
    const suffix = search.toString();
    return suffix ? `/franchises?${suffix}` : "/franchises";
  };

  return <PageShell active="franchises" heading={{ eyebrow: t("franchise.eyebrow"), title: t("franchise.title"), subtitle: t("franchise.subtitle") }}>
    <form className={discovery.searchRow} action="/franchises" role="search">
      <input name="q" defaultValue={query} aria-label={t("search.franchises")} placeholder={t("search.franchises")} />
      <button type="submit">{t("common.search")}</button>
    </form>
    {data.results.length ? (
      <div className={styles.grid}>
        {data.results.map(item => (
          <Link className={styles.card} href={`/franchises/${item.slug}`} key={item.slug}>
            <h2>{item.name}</h2>
            <p>{item.description || t("franchise.descriptionMissing")}</p>
            <span>{t("franchise.count", { count: item.title_count })} →</span>
          </Link>
        ))}
      </div>
    ) : (
      <div className="empty-state" role="status">
        <strong>{query ? t("catalog.notFound") : t("franchise.empty")}</strong>
        {query && <Link className="secondary" href="/franchises">{t("catalog.resetFilters")}</Link>}
      </div>
    )}
    {pages > 1 && (
      <nav className={styles.pagination} aria-label={t("franchise.title")}>
        {page > 1 && <Link href={pageHref(page - 1)}>{t("common.back")}</Link>}
        <span>{t("catalog.page", { current: page, total: pages })}</span>
        {page < pages && <Link href={pageHref(page + 1)}>{t("common.next")}</Link>}
      </nav>
    )}
  </PageShell>;
}
