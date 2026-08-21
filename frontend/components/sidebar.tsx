import Link from "next/link";
import { getI18n } from "../i18n/server";

export async function Sidebar({ active }: { active: "home" | "catalog" | "schedule" | "franchises" | "library" }) {
  const { t } = await getI18n();
  const linkClass = (section: typeof active) => section === active ? "active" : undefined;
  return <aside className="sidebar">
    <Link className="brand" href="/">Ani<span>Cast</span></Link>
    <nav aria-label={t("nav.main")}>
      <Link className={linkClass("home")} href="/">{t("nav.home")}</Link>
      <Link className={linkClass("catalog")} href="/catalog">{t("nav.catalog")}</Link>
      <Link className={linkClass("schedule")} href="/schedule">{t("nav.schedule")}</Link>
      <Link className={linkClass("franchises")} href="/franchises">{t("nav.franchises")}</Link>
      <span className="nav-disabled" aria-disabled="true">{t("nav.characters")}</span>
      <span className="nav-disabled" aria-disabled="true">{t("nav.media")}</span>
    </nav>
    <div className="nav-group">
      <small>{t("nav.library")}</small>
      <Link className={linkClass("library")} href="/library">{t("nav.allTitles")}</Link>
      <Link href="/history">{t("nav.history")}</Link>
      <Link href="/library?status=watching">{t("nav.watching")}</Link>
      <Link href="/library?status=planned">{t("nav.planned")}</Link>
      <Link href="/library?status=completed">{t("nav.completed")}</Link>
      <Link href="/library?favorite=true">{t("nav.favorites")}</Link>
      <Link href="/notes">{t("nav.notes")}</Link>
    </div>
  </aside>;
}
