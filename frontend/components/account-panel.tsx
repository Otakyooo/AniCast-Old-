"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { cachedSessionUser, fetchAccountSummary, getSessionUser, type AccountSummary, type SessionUser } from "../lib/auth";
import { ResumeShelf } from "./continue-watching-block";
import { CollectionPreviews } from "./collection-previews";
import { RecommendationShelf } from "./recommendation-shelf";
import { RecentNotes } from "./recent-notes";
import { useI18n } from "./i18n-provider";
import { ViewingActivityChart } from "./viewing-activity-chart";
import authStyles from "../app/auth.module.css";
import styles from "../app/profile.module.css";

export function AccountPanel() {
  const { t } = useI18n();
  // First client render must match the server (loading state); the cached
  // identity is applied post-mount, before the network revalidation lands.
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const cached = cachedSessionUser();
    if (cached !== undefined) setUser(cached);
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

  if (error) return <div className={authStyles.accountState} role="alert"><p>{error}</p><Link href="/">{t("account.home")}</Link></div>;
  if (user === undefined) return <div className={authStyles.accountState} role="status">{t("account.loading")}</div>;
  if (user === null) return <div className={authStyles.accountState}><h2>{t("account.noSession")}</h2><p>{t("account.noSessionText")}</p><Link className={authStyles.submit} href="/login">{t("common.login")}</Link></div>;

  // Stats strip per spec §5.1: exactly five metrics. On-hold/dropped live in
  // the library filters, not here. Library counts deep-link into the filtered
  // library view; hours and rating stay plain.
  const strip: Array<{ labelKey: string; value: number | string; href?: string }> = [
    { labelKey: "nav.completed", value: summary?.library.completed ?? "—", href: "/library?status=completed" },
    { labelKey: "nav.watching", value: summary?.library.watching ?? "—", href: "/library?status=watching" },
    { labelKey: "nav.planned", value: summary?.library.planned ?? "—", href: "/library?status=planned" },
    { labelKey: "profile.statsHours", value: summary ? summary.watched_hours : "—" },
    {
      labelKey: "profile.statsAvgRating",
      value: summary?.average_rating != null ? summary.average_rating.toFixed(1) : "—",
    },
  ];

  const quickLinks: Array<{ href: string; titleKey: string; hint?: string }> = [
    {
      href: "/library?view=collections",
      titleKey: "collections.title",
      hint: summary ? t("account.sectionCollectionsHint", { count: summary.collections }) : undefined,
    },
    { href: "/recommendations", titleKey: "recommendations.title", hint: t("account.sectionRecommendationsHint") },
    { href: "/settings", titleKey: "settings.title", hint: t("account.sectionSettingsHint") },
  ];

  return (
    <div className={styles.overview}>
      <section className={styles.strip} aria-label={t("account.statsLabel")}>
        {strip.map((item) =>
          item.href ? (
            <Link className={`${styles.stripItem} ${styles.stripItemLink}`} href={item.href} key={item.labelKey}>
              <span className={styles.stripValue}>{item.value}</span>
              <span className={styles.stripLabel}>{t(item.labelKey)}</span>
            </Link>
          ) : (
            <div className={styles.stripItem} key={item.labelKey}>
              <span className={styles.stripValue}>{item.value}</span>
              <span className={styles.stripLabel}>{t(item.labelKey)}</span>
            </div>
          ),
        )}
      </section>

      {summary && <ViewingActivityChart activity={summary.activity} />}

      <ResumeShelf />

      <CollectionPreviews />

      {(summary?.top_genres.length ?? 0) > 0 && (
        <section aria-label={t("profile.favoriteGenres")}>
          <div className={styles.sectionHeading}><h2>{t("profile.favoriteGenres")}</h2></div>
          <ul className={styles.genreList}>
            {summary?.top_genres.map((genre) => (
              <li key={genre.slug}>
                <Link
                  className={styles.genreRow}
                  href={`/catalog?genre=${genre.slug}`}
                  title={t("profile.genreToCatalog")}
                >
                  <span className={styles.genreName}>{genre.name}</span>
                  <span className={styles.genreTrack}>
                    <span className={styles.genreBar} style={{ width: `${genre.share}%` }} />
                  </span>
                  <span className={styles.genreCount}>{t("profile.genreCount", { count: genre.count })}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <RecommendationShelf />

      <RecentNotes />

      <section aria-label={t("account.sections")}>
        <div className={styles.grid}>
          {quickLinks.map((link) => (
            <Link className={styles.sectionCard} key={link.href} href={link.href}>
              <span className={styles.sectionTitle}>{t(link.titleKey)}</span>
              <span className={styles.sectionCount}>
                {link.hint}
                <span aria-hidden="true">→</span>
              </span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
