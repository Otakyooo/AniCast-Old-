import Link from "next/link";

export function Sidebar({ active }: { active: "home" | "catalog" | "library" }) {
  const linkClass = (section: typeof active) => section === active ? "active" : undefined;
  return <aside className="sidebar">
    <Link className="brand" href="/">Ani<span>Cast</span></Link>
    <nav aria-label="Основная навигация">
      <Link className={linkClass("home")} href="/">Главная</Link>
      <Link className={linkClass("catalog")} href="/catalog">Каталог</Link>
      <span className="nav-disabled" aria-disabled="true">Расписание</span>
      <span className="nav-disabled" aria-disabled="true">Франшизы</span>
      <span className="nav-disabled" aria-disabled="true">Персонажи</span>
      <span className="nav-disabled" aria-disabled="true">Медиа</span>
    </nav>
    <div className="nav-group">
      <small>МОЯ БИБЛИОТЕКА</small>
      <Link className={linkClass("library")} href="/library">Все тайтлы</Link>
      <Link href="/library?status=watching">Смотрю</Link>
      <Link href="/library?status=planned">Запланировано</Link>
      <Link href="/library?status=completed">Просмотрено</Link>
      <Link href="/library?favorite=true">Избранное</Link>
      <span className="nav-disabled" aria-disabled="true">Заметки</span>
    </div>
  </aside>;
}
