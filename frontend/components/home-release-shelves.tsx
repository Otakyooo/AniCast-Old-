"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo } from "react";
import type { CatalogItem, ScheduleItem } from "../lib/api";
import { planRecentEpisodeShelf } from "../lib/home-shelves";
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
 * Both rails answer the daily viewer's real questions first — "what just came
 * out" and "what is airing now with the next episode date" — ahead of
 * franchise discovery. Times stay hidden until the browser timezone is known
 * so the first paint matches the server markup.
 *
 * The release shelf is fed a wider window than one week and picks how much of
 * it to show: a thin week is filled with older releases, and a window that
 * cannot fill a rail row at all becomes a compact block instead of a
 * poster-height gap.
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
  const timeFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { hour: "2-digit", minute: "2-digit" }),
    [locale],
  );

  if (items.length === 0) return null;
  const todayKey = clock.local ? localDayKey(new Date(clock.now)) : serverTodayKey;
  const plan = planRecentEpisodeShelf(items, todayKey);
  if (plan.items.length === 0) return null;

  /** "Сегодня" / "20 окт." plus the exact time once the timezone is known. */
  const releaseWhen = (item: ScheduleItem) => {
    const moment = item.air_at ? new Date(item.air_at) : null;
    const hasTime = moment !== null && !Number.isNaN(moment.getTime());
    // Day-only rows fall back to their date; the exact time is never
    // invented for them.
    const dayKey = (item.air_date ?? "").slice(0, 10);
    const day = dayKey === todayKey
      ? t("home.today")
      : dayKey
        ? dayFormatter.format(new Date(`${dayKey}T12:00:00Z`))
        : "";
    const time = clock.local && hasTime && moment ? timeFormatter.format(moment) : "";
    return [day, time].filter(Boolean).join(" · ");
  };

  return (
    <section className="section" aria-label={t("home.recentEpisodes")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("home.recentEpisodes")}</h2>
          {/* The subtitle states the window actually shown: claiming "last
              week" over month-old releases would be a lie. */}
          <p>{t(plan.widened ? "home.recentEpisodesTextWide" : "home.recentEpisodesText")}</p>
        </div>
        <Link href="/schedule">{t("home.showAll")}</Link>
      </div>
      {/* Too few releases to fill a rail row: compact rows keep the block as
          small as its data instead of reserving poster height. */}
      {plan.compact ? (
        <ul className={styles.releaseCompactList}>
          {plan.items.map((item) => (
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
                  <strong>{item.title.name}</strong>
                  <small>
                    {[t("episode.number", { number: item.number }), releaseWhen(item)]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <RailScroller railClassName={styles.posterRail}>
          <ul className={styles.railList}>
            {plan.items.map((item) => (
              <li key={item.id}>
                <Link
                  className={styles.releaseCard}
                  href={titleWatchHref(item.title.slug, item.number)}
                  title={`${item.title.name} · ${t("episode.number", { number: item.number })}`}
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
                  </span>
                  <span className={styles.releaseBody}>
                    <strong>{item.title.name}</strong>
                    <small>{releaseWhen(item)}</small>
                  </span>
                </Link>
              </li>
            ))}
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
