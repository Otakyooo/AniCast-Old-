const sections = ["Главная", "Каталог", "Расписание", "Франшизы", "Персонажи", "Медиа"];

export default function HomePage() {
  return <main className="shell">
    <aside className="sidebar"><div className="brand">Ani<span>Cast</span></div><nav aria-label="Основная навигация">{sections.map((item, index) => <a className={index === 0 ? "active" : ""} href="#" key={item}>{item}</a>)}</nav><div className="nav-group"><small>МОЯ БИБЛИОТЕКА</small>{["Смотрю", "Запланировано", "Просмотрено", "Избранное", "Заметки"].map(item => <a href="#" key={item}>{item}</a>)}</div></aside>
    <section className="content"><header className="topbar"><label className="search"><span aria-hidden="true">⌕</span><input aria-label="Поиск по AniCast" placeholder="Поиск тайтлов, персонажей, франшиз..." /></label><button className="profile">Войти</button></header><div className="hero"><p className="eyebrow">ТВОЯ АНИМЕ-БИБЛИОТЕКА</p><h1>Продолжи свой путь</h1><p className="muted">Изучай миры, сохраняй личный контекст и возвращайся к просмотру.</p><button className="primary">Открыть каталог</button></div><section className="section"><div className="section-heading"><h2>Открывай новое</h2><a href="#">Весь каталог →</a></div><div className="empty-state"><strong>Каталог готовится</strong><span>Скоро здесь появятся тайтлы, франшизы и новые эпизоды AniCast.</span></div></section></section>
  </main>;
}
