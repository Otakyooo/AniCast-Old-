import Link from "next/link";
import { cookies } from "next/headers";
import { getI18n } from "../i18n/server";
import { BrandLockup } from "./brand-lockup";
import { GlobalSearch } from "./global-search";
import { NavScrollState } from "./nav-scroll-state";
import { UserMenu } from "./user-menu";

export type NavSection =
  | "home" | "catalog" | "schedule" | "franchises" | "collections" | "characters"
  | "media" | "community" | "profile" | "library";

// The desktop header carries the three watching routes and nothing else. The
// secondary links (franchises / collections / community) were removed from the
// header on purpose, so no dropdown is left behind it: community lives in the
// footer, and franchises/collections stay reachable from the catalog and from
// title pages.
//
// Personal routes are not in the top nav by design, and the library is not
// either: it lives inside the profile (design freeze v0.2, acceptance #2) and
// the account menu links it directly, so a header entry only repeated it.
//
// Order is logo -> nav -> search -> user. The search has a fixed footprint and
// is pushed right, so the free space lands between the nav and the field
// instead of stretching the field across the whole header.
export async function SiteHeader({ active }: { active: NavSection }) {
  const { t } = await getI18n();
  // Presence of the session cookie decides the first paint only. The client
  // component confirms the real session, so a stale cookie cannot grant access.
  const hasSessionCookie = Boolean((await cookies()).get("sessionid")?.value);
  const linkClass = (section: NavSection) => section === active ? "active" : undefined;

  return (
    <header className="global-nav">
      <NavScrollState />
      <div className="global-nav-inner">
        <BrandLockup className="global-brand" priority />
        <nav className="primary-nav" aria-label={t("nav.main")}>
          <Link className={linkClass("home")} href="/">{t("nav.home")}</Link>
          <Link className={linkClass("catalog")} href="/catalog">{t("nav.catalog")}</Link>
          <Link className={linkClass("schedule")} href="/schedule">{t("nav.schedule")}</Link>
        </nav>
        <div className="header-search"><GlobalSearch /></div>
        <div className="global-actions">
          <UserMenu initialSignedIn={hasSessionCookie} />
        </div>
      </div>
    </header>
  );
}
