"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchAccountSummary, getSessionUser, signOut, type AccountSummary, type SessionUser } from "../lib/auth";
import { ContinueWatchingShelf } from "./continue-watching-shelf";
import { NotificationPanel } from "./notification-panel";
import { RecentNotes } from "./recent-notes";
import { useI18n } from "./i18n-provider";
import styles from "../app/profile.module.css";
import authStyles from "../app/auth.module.css";

type SectionLink = {
  href: string;
  titleKey: string;
  countKey: string;
  count?: number;
};

export function AccountPanel({ notificationBotUsername }: { notificationBotUsername?: string }) {
  const router = useRouter();
  const { t } = useI18n();
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getSessionUser().then(setUser).catch((reason) => setError(reason instanceof Error ? reason.message : t("common.error")));
  }, [t]);

  useEffect(() => {
    if (!user) return;
    let alive = true;
    fetchAccountSummary()
      .then((data) => alive && setSummary(data))
      .catch(() => alive && setSummary(null));
    return () => {
      alive = false;
    };
  }, [user]);

  async function logout() {
    setError("");
    try {
      await signOut();
      router.push("/");
      router.refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("common.error"));
    }
  }

  if (error) return <div className={authStyles.accountState} role="alert"><p>{error}</p><Link href="/">{t("account.home")}</Link></div>;
  if (user === undefined) return <div className={authStyles.accountState} role="status">{t("account.loading")}</div>;
  if (user === null) return <div className={authStyles.accountState}><h2>{t("account.noSession")}</h2><p>{t("account.noSessionText")}</p><Link className={authStyles.submit} href="/login">{t("common.login")}</Link></div>;

  const libraryTotal = summary ? Object.values(summary.library).reduce((sum, value) => sum + value, 0) : undefined;
  const sections: SectionLink[] = [
    { href: "/library", titleKey: "library.title", countKey: "account.sectionLibraryHint", count: libraryTotal },
    { href: "/history", titleKey: "history.title", countKey: "account.sectionHistoryHint", count: summary?.watched_episodes },
    { href: "/notes", titleKey: "notes.title", countKey: "account.sectionNotesHint", count: summary?.notes },
    { href: "/collections", titleKey: "collections.title", countKey: "account.sectionCollectionsHint", count: summary?.collections },
    { href: "/recommendations", titleKey: "recommendations.title", countKey: "account.sectionRecommendationsHint" },
  ];

  const stats: Array<{ labelKey: string; value?: number }> = [
    { labelKey: "nav.watching", value: summary?.library.watching },
    { labelKey: "nav.planned", value: summary?.library.planned },
    { labelKey: "nav.completed", value: summary?.library.completed },
    { labelKey: "nav.favorites", value: summary?.favorites },
    { labelKey: "account.statsOnHold", value: summary?.library.on_hold },
    { labelKey: "library.dropped", value: summary?.library.dropped },
    { labelKey: "account.statsRatings", value: summary?.ratings },
    { labelKey: "account.statsReviews", value: summary?.reviews },
  ];

  return (
    <div className={styles.hub}>
      <header className={styles.head}>
        <div className={styles.avatar} aria-hidden="true">
          {(user.display_name || t("account.viewer")).trim().charAt(0).toUpperCase()}
        </div>
        <div className={styles.identity}>
          <p className={styles.name}>{user.display_name || t("account.viewer")}</p>
          <p className={styles.email}>{user.email || t("account.noEmail")}</p>
        </div>
        <button className={authStyles.secondary} type="button" onClick={logout}>{t("account.logout")}</button>
      </header>

      <section className={styles.stats} aria-label={t("account.statsLabel")}>
        {stats.map((stat) => (
          <div className={styles.stat} key={stat.labelKey}>
            <span className={styles.statValue}>{stat.value ?? "—"}</span>
            <span className={styles.statLabel}>{t(stat.labelKey)}</span>
          </div>
        ))}
      </section>

      <ContinueWatchingShelf />
      <RecentNotes />

      <section aria-label={t("account.sections")}>
        <div className={styles.grid}>
          {sections.map((section) => (
            <Link className={styles.sectionCard} key={section.href} href={section.href}>
              <span className={styles.sectionTitle}>{t(section.titleKey)}</span>
              <span className={styles.sectionCount}>
                {section.count === undefined ? "" : t(section.countKey, { count: section.count })}
                <span aria-hidden="true">→</span>
              </span>
            </Link>
          ))}
        </div>
      </section>

      <section className={styles.notifications}>
        <NotificationPanel botUsername={notificationBotUsername} />
      </section>
    </div>
  );
}
