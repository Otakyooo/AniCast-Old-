import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { CatalogCard } from "../../../components/catalog-card";
import { PageShell } from "../../../components/page-shell";
import { apiErrorStatus, getFranchise } from "../../../lib/api";
import { metaDescription } from "../../../lib/site";
import { getI18n } from "../../../i18n/server";
import styles from "../franchises.module.css";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const { t } = await getI18n();
  try { const item = await getFranchise(slug); return { title: item.name, description: metaDescription(item.description, t("franchise.subtitle")), alternates: { canonical: `/franchises/${item.slug}` } }; }
  catch { return { title: t("franchise.title") }; }
}

export default async function FranchisePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const { t } = await getI18n();
  let franchise;
  try { franchise = await getFranchise(slug); }
  catch (error) { if (apiErrorStatus(error) === 404) notFound(); return <ApiUnavailableState />; }
  return <PageShell active="franchises" back={{ href: "/franchises", label: t("franchise.title") }}>
    <header className={styles.detailHero}><p className="eyebrow">{t("franchise.label")}</p><h1>{franchise.name}</h1><p>{franchise.description || t("franchise.subtitle")}</p><span>{franchise.year_from ? `${franchise.year_from}${franchise.year_to && franchise.year_to !== franchise.year_from ? `–${franchise.year_to}` : ""}` : ""} · {t("franchise.count", { count: franchise.title_count })}</span></header>
    {franchise.titles.length ? <div className="catalog-grid">{franchise.titles.map((title) => <CatalogCard item={title} key={title.slug} />)}</div> : <div className="empty-state"><strong>{t("franchise.unlinked")}</strong></div>}
  </PageShell>;
}
