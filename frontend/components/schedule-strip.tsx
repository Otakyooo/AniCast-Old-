"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { ScheduleItem } from "../lib/api";
import { itemDayKey, localDayKey, MINUTE_MS, scheduleStatus } from "../lib/schedule";
import { titleWatchHref } from "../lib/seo";
import { useI18n } from "./i18n-provider";
import { intlLocale } from "../i18n/config";
import styles from "../app/home.module.css";

/**
 * Compact "airing next" strip for the home page.
 *
 * Times stay hidden until the browser timezone is known, so the first paint
 * matches the server markup and the viewer never sees a shifted time. The
 * component owns its whole section: when every scheduled episode for the
 * window turns out released, the heading disappears with the empty strip
 * instead of leaving a titled zero-height block on the page.
 */
export function ScheduleStrip({
  items,
  serverTodayKey,
}: { items: ScheduleItem[]; serverTodayKey: string }) {
  const { t, locale } = useI18n();
  const [clock, setClock] = useState<{ now: number; local: boolean }>({
    now: Date.parse(`${serverTodayKey}T00:00:00Z`),
    local: false,
  });

  useEffect(() => {
    setClock({ now: Date.now(), local: true });
    const timer = window.setInterval(() => setClock({ now: Date.now(), local: true }), MINUTE_MS);
    return () => window.clearInterval(timer);
  }, []);

  const todayKey = clock.local ? localDayKey(new Date(clock.now)) : serverTodayKey;
  const timeFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { hour: "2-digit", minute: "2-digit" }),
    [locale],
  );
  const dayFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { weekday: "short", timeZone: "UTC" }),
    [locale],
  );

  const upcoming = useMemo(() => {
    // Only future or currently airing entries belong in this strip; the full
    // schedule page keeps the released ones. Before the timezone is known the
    // day-level status already excludes past days.
    return items
      .filter((item) => scheduleStatus(item, clock.now, todayKey, clock.local).kind !== "released")
      .slice(0, 8);
  }, [items, clock.now, clock.local, todayKey]);

  if (!upcoming.length) return null;

  return (
    <section className="section" aria-label={t("schedule.title")}>
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{t("schedule.title")}</h2>
          <p>{t("schedule.subtitle")}</p>
        </div>
        <Link href="/schedule">{t("home.showAll")}</Link>
      </div>
      <ul className={styles.scheduleStrip}>
        {upcoming.map((item) => {
          const status = scheduleStatus(item, clock.now, todayKey, clock.local);
          const dayKey = itemDayKey(item, clock.local);
          const moment = item.air_at ? new Date(item.air_at) : null;
          const hasTime = moment !== null && !Number.isNaN(moment.getTime());
          const when = dayKey === todayKey
            ? t("schedule.today")
            : dayFormatter.format(new Date(`${dayKey}T12:00:00Z`));
          return (
            <li key={item.id}>
              <Link className={styles.scheduleCard} href={titleWatchHref(item.title.slug, item.number)}>
                <span className={styles.schedulePoster}>
                  {item.title.poster_url ? (
                    <Image
                      className={styles.resumeImage}
                      src={item.title.poster_url}
                      alt=""
                      fill
                      sizes="64px"
                      quality={92}
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <span className={styles.resumeFallback} aria-hidden="true">
                      {item.title.name.slice(0, 1).toUpperCase()}
                    </span>
                  )}
                </span>
                <span className={styles.scheduleBody}>
                  <strong>{item.title.name}</strong>
                  <small>{t("episode.number", { number: item.number })}</small>
                  <span className={styles.scheduleWhen}>
                    {when}
                    {clock.local && hasTime ? ` · ${timeFormatter.format(moment)}` : ""}
                  </span>
                  {status.kind === "airing" && <span className={styles.scheduleNow}>{t("schedule.airingNow")}</span>}
                  {status.kind === "minutes" && (
                    <span className={styles.scheduleSoon}>{t("schedule.inMinutes", { count: status.minutes })}</span>
                  )}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
