import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { CatalogCard } from "../../../components/catalog-card";
import { PageShell } from "../../../components/page-shell";
import { apiErrorStatus, getFranchise } from "../../../lib/api";
import { NO_INDEX_ROBOTS } from "../../../lib/seo";
import { absoluteUrl, metaDescription } from "../../../lib/site";
import { getI18n } from "../../../i18n/server";
import styles from "../franchises.module.css";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const { t } = await getI18n();
  try {
    const item = await getFranchise(slug);
    const description = metaDescription(item.description, t("franchise.subtitle"));
    const canonical = `/franchises/${item.slug}`;
    const poster = item.titles.find((title) => title.poster_url)?.poster_url;
    return {
      title: item.name,
      description,
      alternates: { canonical },
      openGraph: {
        type: "website",
        url: canonical,
        title: item.name,
        description,
        ...(poster ? { images: [{ url: absoluteUrl(poster), alt: item.name }] } : {}),
      },
    };
  } catch (error) {
    // A degraded API renders the unavailable shell at 200; that page must not
    // take the franchise's place in the index.
    if (apiErrorStatus(error) === 404) return { title: t("franchise.title") };
    return {
      title: t("franchise.title"),
      alternates: { canonical: `/franchises/${encodeURIComponent(slug)}` },
      robots: NO_INDEX_ROBOTS,
    };
  }
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
