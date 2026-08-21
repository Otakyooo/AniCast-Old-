import Link from "next/link";
import { getI18n } from "../i18n/server";
import { AccountLink } from "./account-link";

type Section = "home" | "catalog" | "schedule" | "franchises" | "characters" | "media" | "community" | "library" | "collections";

export async function Sidebar({ active }: { active: Section }) {
  const { t } = await getI18n();
  const linkClass = (section: Section) => section === active ? "active" : undefined;

  return <>
    <header className="global-nav">
      <div className="global-nav-inner">
        <Link className="global-brand" href="/" aria-label="AniCast">
          <span className="brand-mark" aria-hidden="true">A</span><span>Ani<b>Cast</b></span>
        </Link>
        <nav className="primary-nav" aria-label={t("nav.main")}>
          <Link className={linkClass("home")} href="/">{t("nav.home")}</Link>
          <Link className={linkClass("catalog")} href="/catalog">{t("nav.catalog")}</Link>
          <Link className={linkClass("schedule")} href="/schedule">{t("nav.schedule")}</Link>
          <Link className={linkClass("franchises")} href="/franchises">{t("nav.franchises")}</Link>
          <Link className={linkClass("characters")} href="/characters">{t("nav.characters")}</Link>
          <details className={`more-nav ${["media", "community", "library", "collections"].includes(active) ? "active" : ""}`}>
            <summary>{t("nav.more")}</summary>
            <div className="more-menu">
              <Link className={`compact-only ${linkClass("characters") ?? ""}`} href="/characters">{t("nav.characters")}</Link>
              <Link className={linkClass("media")} href="/media">{t("nav.media")}</Link>
              <Link className={linkClass("community")} href="/community">{t("nav.community")}</Link>
              <Link className={linkClass("library")} href="/library">{t("nav.libraryShort")}</Link>
              <Link className={linkClass("collections")} href="/collections">{t("nav.collections")}</Link>
              <Link href="/recommendations">{t("nav.recommendations")}</Link>
            </div>
          </details>
        </nav>
        <form className="global-search" action="/catalog">
          <span aria-hidden="true">⌕</span>
          <input name="q" aria-label={t("catalog.searchLabel")} placeholder={t("catalog.searchPlaceholder")} />
          <kbd>⌘K</kbd>
        </form>
        <div className="global-actions">
          <Link className="notification-link" href="/account" aria-label={t("nav.notifications")}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></svg>
          </Link>
          <AccountLink />
        </div>
      </div>
    </header>
    <nav className="mobile-bottom-nav" aria-label={t("nav.main")}>
      <Link className={linkClass("home")} href="/"><span aria-hidden="true">⌂</span>{t("nav.home")}</Link>
      <Link className={linkClass("catalog")} href="/catalog"><span aria-hidden="true">▦</span>{t("nav.catalog")}</Link>
      <Link className={linkClass("schedule")} href="/schedule"><span aria-hidden="true">◫</span>{t("nav.schedule")}</Link>
      <Link href="/catalog"><span aria-hidden="true">⌕</span>{t("nav.search")}</Link>
      <Link className={linkClass("library")} href="/account"><span aria-hidden="true">○</span>{t("nav.profile")}</Link>
    </nav>
  </>;
}
