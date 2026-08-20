import Link from "next/link";
import { getCatalog, type CatalogItem } from "../../lib/api";

export const dynamic = "force-dynamic";

function statusLabel(status?: string | null) {
  const labels: Record<string, string> = { ongoing: "Выходит", finished: "Завершено", planned: "Скоро" };
  return status ? labels[status] ?? status : "Аниме";
}

function CatalogCard({ item }: { item: CatalogItem }) {
  return (
    <Link className="catalog-card" href={`/titles/${item.slug}`}>
      <div className="poster-placeholder" style={{ "--poster-accent": "#6d5dfb" } as React.CSSProperties} aria-hidden="true">
        <span>{item.name.slice(0, 1).toUpperCase()}</span>
      </div>
      <div className="catalog-card-body">
        <span className="card-kicker">{statusLabel(item.status)}</span>
        <h2>{item.name}</h2>
        <p>{item.year ?? "Год не указан"}{item.title_type ? ` · ${item.title_type}` : ""}</p>
      </div>
    </Link>
  );
}

export default async function CatalogPage({ searchParams }: { searchParams: Promise<{ search?: string }> }) {
  const { search } = await searchParams;
  const catalog = await getCatalog(search);

  return <main className="shell">
    <aside className="sidebar"><Link className="brand" href="/">Ani<span>Cast</span></Link><nav aria-label="Основная навигация"><Link href="/">Главная</Link><Link className="active" href="/catalog" aria-current="page">Каталог</Link><span className="nav-disabled" aria-disabled="true">Расписание</span><span className="nav-disabled" aria-disabled="true">Франшизы</span><span className="nav-disabled" aria-disabled="true">Персонажи</span><span className="nav-disabled" aria-disabled="true">Медиа</span></nav><div className="nav-group"><small>МОЯ БИБЛИОТЕКА</small>{["Смотрю", "Запланировано", "Просмотрено", "Избранное", "Заметки"].map(item => <span className="nav-disabled" aria-disabled="true" key={item}>{item}</span>)}</div></aside>
    <section className="content"><header className="topbar"><form className="search" action="/catalog"><span aria-hidden="true">⌕</span><input name="q" defaultValue={search} aria-label="Поиск по каталогу" placeholder="Поиск тайтлов, персонажей, франшиз..." /><button type="submit" className="search-submit">Найти</button></form><button className="profile">Войти</button></header>
      <div className="page-heading"><p className="eyebrow">КОЛЛЕКЦИЯ ANICAST</p><h1>Каталог</h1><p className="muted">Находи новые миры и собирай библиотеку, к которой хочется возвращаться.</p></div>
      {catalog.results.length ? <div className="catalog-grid">{catalog.results.map(item => <CatalogCard item={item} key={item.id} />)}</div> : <div className="empty-state" role="status"><strong>{search ? "Ничего не найдено" : "Каталог пока пуст"}</strong><span>{search ? "Попробуй изменить запрос или посмотреть всю коллекцию." : "Скоро здесь появятся тайтлы AniCast."}</span>{search && <Link className="secondary" href="/catalog">Сбросить поиск</Link>}</div>}
    </section>
  </main>;
}
