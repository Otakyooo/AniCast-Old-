"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fetchAccountSummary, getSessionUser, type AccountSummary, type SessionUser } from "../lib/auth";
import { ResumeShelf } from "./continue-watching-block";
import { CollectionPreviews } from "./collection-previews";
import { RecommendationShelf } from "./recommendation-shelf";
import { RecentNotes } from "./recent-notes";
import { useI18n } from "./i18n-provider";
import { ViewingActivityChart } from "./viewing-activity-chart";
import authStyles from "../app/auth.module.css";
import styles from "../app/profile.module.css";

/** Below this many watched episodes the activity chart is two lonely bars
 * pretending to be analytics; it stays hidden until real history exists. */
const MIN_EPISODES_FOR_CHART = 8;

/** Fewer library titles than this make "favorite genres" fake statistics. */
const MIN_TITLES_FOR_GENRES = 10;

export function AccountPanel() {
  const { t } = useI18n();
  // Match SSR and show private data only after the session is revalidated.
  const [user, setUser] = useState<SessionUser | null | undefined>();
  const [summary, setSummary] = useState<AccountSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getSessionUser()
      .then((value) => { if (active) setUser(value); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : t("common.error")); });
    return () => { active = false; };
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

  // Compact single stats line: "Просмотрено 3 · Смотрю 0 · …". The dashboard
  // box existed for its own sake; one reading line carries the same facts.
  const libraryTotal = summary
    ? Object.values(summary.library).reduce((sum, count) => sum + count, 0)
    : 0;
  const stats: Array<{ labelKey: string; value: number | string; href?: string }> = [
    { labelKey: "nav.completed", value: summary?.library.completed ?? "—", href: "/library?status=completed" },
    { labelKey: "nav.watching", value: summary?.library.watching ?? "—", href: "/library?status=watching" },
    { labelKey: "nav.planned", value: summary?.library.planned ?? "—", href: "/library?status=planned" },
    { labelKey: "profile.statsHours", value: summary ? summary.watched_hours : "—" },
    {
      labelKey: "profile.statsAvgRating",
      value: summary?.average_rating != null ? summary.average_rating.toFixed(1) : "—",
    },
  ];

  return (
    <div className={styles.overview}>
      {/* The profile's job is to resume watching, not to admire a dashboard:
          Continue Watching comes right after the header. */}
      <ResumeShelf />

      <section className={styles.statsLine} aria-label={t("account.statsLabel")}>
        {stats.map((item) =>
          item.href ? (
            <Link className={styles.statsItem} href={item.href} key={item.labelKey}>
              <strong>{item.value}</strong> {t(item.labelKey)}
            </Link>
          ) : (
            <span className={styles.statsItem} key={item.labelKey}>
              <strong>{item.value}</strong> {t(item.labelKey)}
            </span>
          ),
        )}
      </section>

      {summary && (summary.watched_episodes ?? 0) >= MIN_EPISODES_FOR_CHART && (
        <ViewingActivityChart activity={summary.activity} />
      )}

      <CollectionPreviews />

      {libraryTotal >= MIN_TITLES_FOR_GENRES && (summary?.top_genres.length ?? 0) > 0 && (
        <section aria-label={t("profile.favoriteGenres")}>
          <div className={styles.sectionHeading}><h2>{t("profile.favoriteGenres")}</h2></div>
          {/* Compact chips instead of full-width bars: the fact is the count,
              not the shape of a progress track. */}
          <ul className={styles.genreChips}>
            {summary?.top_genres.map((genre) => (
              <li key={genre.slug}>
                <Link className={styles.genreChip} href={`/catalog?genre=${genre.slug}`} title={t("profile.genreToCatalog")}>
                  {genre.name} <span>{genre.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <RecommendationShelf />

      <RecentNotes />
    </div>
  );
}
