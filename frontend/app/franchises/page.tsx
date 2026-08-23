import Link from "next/link";
import { PageShell } from "../../components/page-shell";
import { emptyPage, getFranchises, type FranchiseResponse } from "../../lib/api";
import { getI18n } from "../../i18n/server";
import styles from "./franchises.module.css";

export const dynamic = "force-dynamic";

export default async function FranchisesPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const rawPage = Number.parseInt((await searchParams).page ?? "1", 10);
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const data = await getFranchises(page).catch((): FranchiseResponse => emptyPage());
  const { t } = await getI18n();
  const pages = Math.max(1, Math.ceil(data.count / 20));

  return <PageShell active="franchises" heading={{ eyebrow: t("franchise.eyebrow"), title: t("franchise.title"), subtitle: t("franchise.subtitle") }}>
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
      <div className="empty-state"><strong>{t("franchise.empty")}</strong></div>
    )}
    {pages > 1 && (
      <nav className={styles.pagination}>
        {page > 1 && <Link href={`/franchises?page=${page - 1}`}>{t("common.back")}</Link>}
        <span>{t("catalog.page", { current: page, total: pages })}</span>
        {page < pages && <Link href={`/franchises?page=${page + 1}`}>{t("common.next")}</Link>}
      </nav>
    )}
  </PageShell>;
}
