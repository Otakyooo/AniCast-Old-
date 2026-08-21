import Link from "next/link";
import { AccountLink } from "../components/account-link";
import { CatalogCard } from "../components/catalog-card";
import { Sidebar } from "../components/sidebar";
import { getCatalog } from "../lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const catalog = await getCatalog({ pageSize: 4 });

  return <main className="shell">
    <Sidebar active="home" />
    <section className="content"><header className="topbar"><form className="search" action="/catalog"><span aria-hidden="true">⌕</span><input name="q" aria-label="Поиск по AniCast" placeholder="Поиск тайтлов, персонажей, франшиз..." /><button type="submit" className="search-submit">Найти</button></form><AccountLink /></header><div className="hero"><p className="eyebrow">ТВОЯ АНИМЕ-БИБЛИОТЕКА</p><h1>Продолжи свой путь</h1><p className="muted">Изучай миры, сохраняй личный контекст и возвращайся к просмотру.</p><Link className="primary inline-button" href="/catalog">Открыть каталог</Link></div><section className="section"><div className="section-heading"><h2>Открывай новое</h2><Link href="/catalog">Весь каталог →</Link></div>{catalog.results.length ? <div className="catalog-grid">{catalog.results.map(item => <CatalogCard item={item} key={item.slug} />)}</div> : <div className="empty-state"><strong>Каталог пока пуст</strong><span>Скоро здесь появятся тайтлы, франшизы и новые эпизоды AniCast.</span></div>}</section></section>
  </main>;
}
