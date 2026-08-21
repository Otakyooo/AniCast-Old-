import Link from "next/link";
import { AccountLink } from "../../components/account-link";
import { Sidebar } from "../../components/sidebar";
import { getFranchises } from "../../lib/api";
import styles from "./franchises.module.css";

export const dynamic = "force-dynamic";

export default async function FranchisesPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const rawPage = Number.parseInt((await searchParams).page ?? "1", 10);
  const page = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const data = await getFranchises(page);
  const pages = Math.max(1, Math.ceil(data.count / 20));
  return <main className="shell"><Sidebar active="franchises" /><section className="content"><header className="topbar"><span className="eyebrow">СВЯЗАННЫЕ МИРЫ</span><AccountLink /></header><div className="page-heading"><h1>Франшизы</h1><p className="muted">Серии, фильмы и ответвления, объединённые одной историей.</p></div>{data.results.length ? <div className={styles.grid}>{data.results.map(item => <Link className={styles.card} href={`/franchises/${item.slug}`} key={item.slug}><h2>{item.name}</h2><p>{item.description || "Описание франшизы пока не добавлено."}</p><span>{item.title_count} тайтлов →</span></Link>)}</div> : <div className="empty-state"><strong>Франшизы пока не добавлены</strong></div>}{pages > 1 && <nav className={styles.pagination}>{page > 1 && <Link href={`/franchises?page=${page - 1}`}>← Назад</Link>}<span>{page} из {pages}</span>{page < pages && <Link href={`/franchises?page=${page + 1}`}>Вперёд →</Link>}</nav>}</section></main>;
}
