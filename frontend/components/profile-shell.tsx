import Link from "next/link";
import { cookies } from "next/headers";
import { getI18n } from "../i18n/server";
import { ProfileIdentity } from "./profile-identity";
import styles from "../app/profile.module.css";

export type ProfileTab = "overview" | "library" | "history";

const TABS: Array<{ id: ProfileTab; href: string; labelKey: string }> = [
  { id: "overview", href: "/account", labelKey: "profile.tabOverview" },
  { id: "library", href: "/library", labelKey: "profile.tabLibrary" },
  { id: "history", href: "/history", labelKey: "profile.tabHistory" },
];

/**
 * Shared frame of the personal area (design spec §5): one banner with the
 * identity block and one tab bar rendered by every personal route, so
 * /account, /library and /history read as a single profile instead of
 * separate sites. Achievements stay out per spec §7.2 until gamification
 * actually ships.
 */
export async function ProfileShell({ tab, children }: { tab: ProfileTab; children: React.ReactNode }) {
  const { t } = await getI18n();
  // Presence of the session cookie decides the first paint only; the client
  // identity probe confirms the real session.
  const hasSessionCookie = Boolean((await cookies()).get("sessionid")?.value);

  return (
    <div className={styles.profilePage}>
      <div className={styles.bannerCard}>
        <div className={styles.banner} aria-hidden="true" />
        <header className={styles.header}>
          <ProfileIdentity initialSignedIn={hasSessionCookie} />
        </header>
        <nav className={styles.tabs} aria-label={t("account.sections")}>
          {TABS.map((item) =>
            item.id === tab ? (
              <span className={`${styles.tab} ${styles.tabActive}`} key={item.href} aria-current="page">
                {t(item.labelKey)}
              </span>
            ) : (
              <Link className={styles.tab} href={item.href} key={item.href}>{t(item.labelKey)}</Link>
            ),
          )}
        </nav>
      </div>
      {children}
    </div>
  );
}
