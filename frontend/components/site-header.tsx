import Link from "next/link";
import { cookies } from "next/headers";
import { getI18n } from "../i18n/server";
import { GlobalSearch } from "./global-search";
import { UserMenu } from "./user-menu";

export type NavSection =
  | "home" | "catalog" | "schedule" | "franchises" | "characters"
  | "media" | "community" | "library" | "collections";

const OVERFLOW_SECTIONS: NavSection[] = ["media", "community", "library", "collections"];

export async function SiteHeader({ active }: { active: NavSection }) {
  const { t } = await getI18n();
  // Presence of the session cookie decides the first paint only. The client
  // component confirms the real session, so a stale cookie cannot grant access.
  const hasSessionCookie = Boolean((await cookies()).get("sessionid")?.value);
  const linkClass = (section: NavSection) => section === active ? "active" : undefined;

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
          <details className={`more-nav ${OVERFLOW_SECTIONS.includes(active) ? "active" : ""}`}>
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
        <GlobalSearch />
        <div className="global-actions">
          <UserMenu initialSignedIn={hasSessionCookie} />
        </div>
      </div>
    </header>
    <nav className="mobile-bottom-nav" aria-label={t("nav.main")}>
      <Link className={linkClass("home")} href="/"><span aria-hidden="true">⌂</span>{t("nav.home")}</Link>
      <Link className={linkClass("catalog")} href="/catalog"><span aria-hidden="true">▦</span>{t("nav.catalog")}</Link>
      <Link className={linkClass("schedule")} href="/schedule"><span aria-hidden="true">◫</span>{t("nav.schedule")}</Link>
      <Link className={linkClass("library")} href="/library"><span aria-hidden="true">▤</span>{t("nav.libraryShort")}</Link>
      <Link href="/account"><span aria-hidden="true">○</span>{t("nav.profile")}</Link>
    </nav>
  </>;
}
