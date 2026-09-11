"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo } from "react";
import type { CatalogItem, ScheduleItem } from "../lib/api";
import { groupRecentEpisodesByTitle, planRecentEpisodeShelf } from "../lib/home-shelves";
import { localDayKey } from "../lib/schedule";
import { titleWatchHref } from "../lib/seo";
import { RailScroller } from "./rail-scroller";
import { useLocalClock } from "../lib/use-local-clock";
import { useI18n } from "./i18n-provider";
import { intlLocale } from "../i18n/config";
import styles from "../app/home.module.css";

/**
 * Release-driven shelves for the home page.
 *
 * «Новые серии» answers "what aired this week" strictly: only episodes whose
 * air date is inside the promised window, grouped to one card per title. A
 * week thinner than the rail falls back to compact rows, never to older
 * releases outside the window.
 */
export function RecentEpisodesRail({
  items,
  serverTodayKey,
}: {
  items: ScheduleItem[];
  serverTodayKey: string;
}) {
  const { t, locale } = useI18n();
  const clock = useLocalClock(serverTodayKey);

  const dayFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { day: "numeric", month: "short" }),
    [locale],
  );

  if (items.length === 0) return null;
  const todayKey = clock.local ? localDayKey(new Date(clock.now)) : serverTodayKey;
  const plan = planRecentEpisodeShelf(items, todayKey);
  if (plan.items.length === 0) return null;
  const groups = groupRecentEpisodesByTitle(plan.items);

  /** Card date label: "Сегодня" / "вчера"-style relative when the day fits. */
  const releaseWhen = (dayKey: string) => {
    const today = todayKey === dayKey ? t("home.today") : dayKey
      ? dayFormatter.format(new Date(`${dayKey}T12:00:00Z`))
      : "";
    return today;
  };

  return (
    <section className="section" aria-label={t("home.recentEpisodes")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.recentEpisodes")}</h2>
          <p>{t("home.recentEpisodesText")}</p>
        </div>
        <Link href="/schedule">{t("home.showAll")}</Link>
      </div>
      {plan.compact ? (
        <ul className={styles.releaseCompactList}>
          {groups.map((group) => {
            const item = group.latest;
            return (
              <li key={item.id}>
                <Link
                  className={styles.releaseCompactCard}
                  href={titleWatchHref(item.title.slug, item.number)}
                >
                  <span className={styles.releaseCompactPoster}>
                    {item.title.poster_url ? (
                      <Image
                        className={styles.releasePosterArt}
                        src={item.title.poster_url}
                        alt=""
                        fill
                        sizes="44px"
                        quality={92}
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <span aria-hidden="true">{item.title.name.slice(0, 1).toUpperCase()}</span>
                    )}
                  </span>
                  <span className={styles.releaseCompactBody}>
                    <strong>
                      {item.title.name}
                      {group.extraCount > 0 && (
                        <span className={styles.releaseCompactExtra}>
                          {" "}· {t("home.moreEpisodes", { count: group.extraCount })}
                        </span>
                      )}
                    </strong>
                    <small>
                      {[t("episode.number", { number: item.number }), releaseWhen(group.latestAirDate)]
                        .filter(Boolean)
                        .join(" · ")}
                    </small>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <RailScroller railClassName={styles.posterRail}>
          <ul className={styles.railList}>
            {groups.map((group) => {
              const item = group.latest;
              return (
                <li key={item.id}>
                  <Link
                    className={styles.releaseCard}
                    href={titleWatchHref(item.title.slug, item.number)}
                    title={group.extraCount > 0
                      ? `${item.title.name} · ${t("episode.number", { number: item.number })} · +${group.extraCount}`
                      : `${item.title.name} · ${t("episode.number", { number: item.number })}`}
                  >
                    <span className={styles.releasePoster}>
                      {item.title.poster_url ? (
                        <Image
                          className={styles.releasePosterArt}
                          src={item.title.poster_url}
                          alt=""
                          fill
                          sizes="(max-width: 767px) 45vw, 220px"
                          quality={92}
                          referrerPolicy="no-referrer"
                        />
                      ) : (
                        <span className={styles.resumeFallback} aria-hidden="true">
                          {item.title.name.slice(0, 1).toUpperCase()}
                        </span>
                      )}
                      <span className={styles.releaseBadge}>
                        {t("episode.number", { number: item.number })}
                      </span>
                      {group.extraCount > 0 && (
                        <span className={styles.releaseBadgeExtra}>+{group.extraCount}</span>
                      )}
                    </span>
                    <span className={styles.releaseBody}>
                      <strong>{item.title.name}</strong>
                      <small>{releaseWhen(group.latestAirDate)}</small>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </RailScroller>
      )}
    </section>
  );
}

export function AiringRail({ items }: { items: CatalogItem[] }) {
  const { t, locale } = useI18n();
  const dayFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { day: "numeric", month: "short" }),
    [locale],
  );

  if (items.length === 0) return null;

  return (
    <section className="section" aria-label={t("home.airingNow")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.airingNow")}</h2>
          <p>{t("home.airingNowText")}</p>
        </div>
        <Link href="/catalog?status=ongoing">{t("home.showAll")}</Link>
      </div>
      <RailScroller railClassName={styles.posterRail}>
        <ul className={styles.railList}>
          {items.map((item) => {
            const nextMoment = item.next_episode_at ? new Date(item.next_episode_at) : null;
            const nextDate = nextMoment !== null && !Number.isNaN(nextMoment.getTime())
              ? dayFormatter.format(nextMoment)
              : "";
            const playable = typeof item.playable_episodes_count === "number"
              ? item.playable_episodes_count
              : null;
            const total = typeof item.episodes_count === "number" ? item.episodes_count : null;
            return (
              <li key={item.slug}>
                <Link
                  className={styles.releaseCard}
                  href={item.last_episode_number ? titleWatchHref(item.slug, item.last_episode_number) : `/titles/${item.slug}`}
                  title={item.name}
                >
                  <span className={styles.releasePoster}>
                    {item.poster_url ? (
                      <Image
                        className={styles.releasePosterArt}
                        src={item.poster_url}
                        alt=""
                        fill
                        sizes="(max-width: 767px) 45vw, 220px"
                        quality={92}
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <span className={styles.resumeFallback} aria-hidden="true">
                        {item.name.slice(0, 1).toUpperCase()}
                      </span>
                    )}
                    {typeof item.last_episode_number === "number" && (
                      <span className={styles.releaseBadge}>
                        {t("episode.number", { number: item.last_episode_number })}
                      </span>
                    )}
                  </span>
                  <span className={styles.releaseBody}>
                    <strong>{item.name}</strong>
                    <small>
                      {nextDate ? t("home.nextEpisodeAt", { date: nextDate }) : t(`status.${item.status ?? "ongoing"}`)}
                    </small>
                    {playable !== null && (
                      <small className={styles.releaseAvailability}>
                        {playable > 0
                          ? total && total > 0
                            ? t("card.playableOf", { available: playable, total })
                            : t("card.playableOnly", { available: playable })
                          : t("card.noPlayable")}
                      </small>
                    )}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </RailScroller>
    </section>
  );
}
