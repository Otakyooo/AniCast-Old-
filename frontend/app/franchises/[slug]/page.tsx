import Link from "next/link";
import { notFound } from "next/navigation";
import { AccountLink } from "../../../components/account-link";
import { CatalogCard } from "../../../components/catalog-card";
import { Sidebar } from "../../../components/sidebar";
import { getFranchise } from "../../../lib/api";
import { getI18n } from "../../../i18n/server";
import styles from "../franchises.module.css";

export const dynamic = "force-dynamic";

export default async function FranchisePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let franchise;
  try { franchise = await getFranchise(slug); } catch { notFound(); }
  const { t } = await getI18n();
  return <main className="shell"><Sidebar active="franchises" /><section className="content"><header className="topbar"><Link className="back-link" href="/franchises">{t("franchise.all")}</Link><AccountLink /></header><div className={styles.hero}><p className="eyebrow">{t("franchise.label")}</p><h1>{franchise.name}</h1><p className="muted">{franchise.description || t("franchise.descriptionMissing")}</p><span className={styles.count}>{t("franchise.count", { count: franchise.title_count })}</span></div>{franchise.titles.length ? <div className="catalog-grid">{franchise.titles.map(title => <CatalogCard item={title} key={title.slug} />)}</div> : <div className="empty-state"><strong>{t("franchise.unlinked")}</strong></div>}</section></main>;
}
