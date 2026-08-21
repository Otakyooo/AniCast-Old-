import Link from "next/link";

export function Sidebar({ active }: { active: "home" | "catalog" | "schedule" | "franchises" | "library" }) {
  const linkClass = (section: typeof active) => section === active ? "active" : undefined;
  return <aside className="sidebar">
    <Link className="brand" href="/">Ani<span>Cast</span></Link>
    <nav aria-label="Основная навигация">
      <Link className={linkClass("home")} href="/">Главная</Link>
      <Link className={linkClass("catalog")} href="/catalog">Каталог</Link>
      <Link className={linkClass("schedule")} href="/schedule">Расписание</Link>
      <Link className={linkClass("franchises")} href="/franchises">Франшизы</Link>
      <span className="nav-disabled" aria-disabled="true">Персонажи</span>
      <span className="nav-disabled" aria-disabled="true">Медиа</span>
    </nav>
    <div className="nav-group">
      <small>МОЯ БИБЛИОТЕКА</small>
      <Link className={linkClass("library")} href="/library">Все тайтлы</Link>
      <Link href="/history">История</Link>
      <Link href="/library?status=watching">Смотрю</Link>
      <Link href="/library?status=planned">Запланировано</Link>
      <Link href="/library?status=completed">Просмотрено</Link>
      <Link href="/library?favorite=true">Избранное</Link>
      <Link href="/notes">Заметки</Link>
    </div>
  </aside>;
}
