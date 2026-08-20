import Link from "next/link";

const sections = [["Главная", "/"], ["Каталог", "/catalog"], ["Расписание", "#"], ["Франшизы", "#"], ["Персонажи", "#"], ["Медиа", "#"]];

export default function HomePage() {
  return <main className="shell">
    <aside className="sidebar"><Link className="brand" href="/">Ani<span>Cast</span></Link><nav aria-label="Основная навигация">{sections.map(([item, href], index) => <Link className={index === 0 ? "active" : ""} href={href} key={item}>{item}</Link>)}</nav><div className="nav-group"><small>МОЯ БИБЛИОТЕКА</small>{["Смотрю", "Запланировано", "Просмотрено", "Избранное", "Заметки"].map(item => <Link href="#" key={item}>{item}</Link>)}</div></aside>
    <section className="content"><header className="topbar"><form className="search" action="/catalog"><span aria-hidden="true">⌕</span><input name="search" aria-label="Поиск по AniCast" placeholder="Поиск тайтлов, персонажей, франшиз..." /><button type="submit" className="search-submit">Найти</button></form><button className="profile">Войти</button></header><div className="hero"><p className="eyebrow">ТВОЯ АНИМЕ-БИБЛИОТЕКА</p><h1>Продолжи свой путь</h1><p className="muted">Изучай миры, сохраняй личный контекст и возвращайся к просмотру.</p><Link className="primary inline-button" href="/catalog">Открыть каталог</Link></div><section className="section"><div className="section-heading"><h2>Открывай новое</h2><Link href="/catalog">Весь каталог →</Link></div><div className="empty-state"><strong>Каталог готовится</strong><span>Скоро здесь появятся тайтлы, франшизы и новые эпизоды AniCast.</span></div></section></section>
  </main>;
}
