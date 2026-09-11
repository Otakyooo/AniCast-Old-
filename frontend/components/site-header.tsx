import Link from "next/link";
import { cookies } from "next/headers";
import { getI18n } from "../i18n/server";
import { BrandLockup } from "./brand-lockup";
import { GlobalSearch } from "./global-search";
import { MobileSearchLink } from "./mobile-search-link";
import { NavMoreMenu } from "./nav-more-menu";
import { UserMenu } from "./user-menu";
import { CalendarDots, House, SquaresFour, UserCircle } from "@phosphor-icons/react/dist/ssr";

export type NavSection =
  | "home" | "catalog" | "schedule" | "franchises" | "collections" | "characters"
  | "media" | "community" | "profile" | "library";

// Personal routes highlight nothing in the desktop top nav by design: the
// library lives inside the profile (design freeze v0.2, acceptance #2).
export async function SiteHeader({ active }: { active: NavSection }) {
  const { t } = await getI18n();
  // Presence of the session cookie decides the first paint only. The client
  // component confirms the real session, so a stale cookie cannot grant access.
  const hasSessionCookie = Boolean((await cookies()).get("sessionid")?.value);
  const linkClass = (section: NavSection) => section === active ? "active" : undefined;

  return (
    <header className="global-nav">
      <div className="global-nav-inner">
        <BrandLockup className="global-brand" priority />
        <nav className="primary-nav" aria-label={t("nav.main")}>
          <Link className={linkClass("home")} href="/">{t("nav.home")}</Link>
          <Link className={linkClass("catalog")} href="/catalog">{t("nav.catalog")}</Link>
          <Link className={linkClass("schedule")} href="/schedule">{t("nav.schedule")}</Link>
          <Link className={linkClass("library")} href="/library">{t("nav.libraryShort")}</Link>
          <NavMoreMenu />
        </nav>
        <div className="header-search"><GlobalSearch /></div>
        <div className="global-actions">
          <UserMenu initialSignedIn={hasSessionCookie} />
        </div>
      </div>
    </header>
  );
}

/**
 * Kept after <main> in the page DOM so keyboard users encounter page content
 * before this visually fixed mobile-only navigation.
 */
export async function MobileBottomNav({ active }: { active: NavSection }) {
  const { t } = await getI18n();
  const linkClass = (section: NavSection) => section === active ? "active" : undefined;

  return (
    <nav className="mobile-bottom-nav" aria-label={t("nav.main")}>
      <Link className={linkClass("home")} href="/"><House aria-hidden="true" size={20} />{t("nav.home")}</Link>
      <Link className={linkClass("catalog")} href="/catalog"><SquaresFour aria-hidden="true" size={20} />{t("nav.catalog")}</Link>
      <Link className={linkClass("schedule")} href="/schedule"><CalendarDots aria-hidden="true" size={20} />{t("nav.schedule")}</Link>
      <MobileSearchLink />
      <Link className={linkClass("profile")} href="/account"><UserCircle aria-hidden="true" size={21} />{t("nav.profile")}</Link>
    </nav>
  );
}
