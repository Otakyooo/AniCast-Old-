import Link from "next/link";
import { notFound } from "next/navigation";
import { AccountLink } from "../../../components/account-link";
import { CatalogCard } from "../../../components/catalog-card";
import { Sidebar } from "../../../components/sidebar";
import { getFranchise } from "../../../lib/api";
import styles from "../franchises.module.css";

export const dynamic = "force-dynamic";

export default async function FranchisePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let franchise;
  try { franchise = await getFranchise(slug); } catch { notFound(); }
  return <main className="shell"><Sidebar active="franchises" /><section className="content"><header className="topbar"><Link className="back-link" href="/franchises">← Все франшизы</Link><AccountLink /></header><div className={styles.hero}><p className="eyebrow">ФРАНШИЗА</p><h1>{franchise.name}</h1><p className="muted">{franchise.description || "Описание пока не добавлено."}</p><span className={styles.count}>{franchise.title_count} тайтлов</span></div>{franchise.titles.length ? <div className="catalog-grid">{franchise.titles.map(title => <CatalogCard item={title} key={title.slug} />)}</div> : <div className="empty-state"><strong>Тайтлы пока не связаны</strong></div>}</section></main>;
}
