"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { ScheduleItem } from "../lib/api";
import {
  addDays,
  groupByDay,
  localDayKey,
  MINUTE_MS,
  scheduleStatus,
  weekDays,
  type ScheduleStatus,
} from "../lib/schedule";
import { useI18n } from "./i18n-provider";
import { intlLocale } from "../i18n/config";
import styles from "../app/schedule/schedule.module.css";

interface ScheduleBoardProps {
  items: ScheduleItem[];
  /** Monday of the rendered week, as YYYY-MM-DD. */
  weekStartKey: string;
  /** Server-rendered "today" so the first paint matches the server markup. */
  serverTodayKey: string;
  prevWeekHref: string;
  nextWeekHref: string;
  thisWeekHref: string;
}

function statusLabel(status: ScheduleStatus, t: (key: string, values?: Record<string, string | number>) => string) {
  switch (status.kind) {
    case "released":
      return t("schedule.released");
    case "airing":
      return t("schedule.airingNow");
    case "minutes":
      return t("schedule.inMinutes", { count: status.minutes });
    case "hours":
      return status.minutes
        ? t("schedule.inHoursMinutes", { hours: status.hours, minutes: status.minutes })
        : t("schedule.inHours", { count: status.hours });
    case "upcoming":
      return t("schedule.upcoming");
    case "pending":
      return t("schedule.laterToday");
    default:
      return t("schedule.timeUnknown");
  }
}

const STATUS_CLASS: Record<ScheduleStatus["kind"], string> = {
  released: styles.statusReleased,
  airing: styles.statusAiring,
  minutes: styles.statusSoon,
  hours: styles.statusSoon,
  upcoming: styles.statusUpcoming,
  pending: styles.statusUpcoming,
  unconfirmed: styles.statusUnknown,
};

export function ScheduleBoard({
  items,
  weekStartKey,
  serverTodayKey,
  prevWeekHref,
  nextWeekHref,
  thisWeekHref,
}: ScheduleBoardProps) {
  const { t, locale } = useI18n();
  // The server cannot know the viewer's timezone, so the first client render
  // repeats the server output and only then switches to local time.
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
  const days = useMemo(() => weekDays(weekStartKey), [weekStartKey]);
  const grouped = useMemo(() => groupByDay(items, clock.local), [items, clock.local]);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const activeDay = selectedDay && days.includes(selectedDay)
    ? selectedDay
    : days.includes(todayKey)
      ? todayKey
      : days[0];
  const dayItems = grouped.get(activeDay) ?? [];
  const boardId = useId();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function onTabsKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    const jump = event.key === "Home" ? 0 : event.key === "End" ? days.length - 1 : null;
    if (!step && jump === null) return;
    event.preventDefault();
    const current = days.indexOf(activeDay);
    const next = jump ?? (current + step + days.length) % days.length;
    setSelectedDay(days[next]);
    tabRefs.current[next]?.focus();
  }

  const dayFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { weekday: "short", timeZone: "UTC" }),
    [locale],
  );
  const fullDayFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }),
    [locale],
  );
  const rangeFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { day: "numeric", month: "short", timeZone: "UTC" }),
    [locale],
  );
  const timeFormatter = useMemo(
    () => new Intl.DateTimeFormat(intlLocale[locale], { hour: "2-digit", minute: "2-digit" }),
    [locale],
  );

  const dayLabel = (dayKey: string) => dayFormatter.format(new Date(`${dayKey}T12:00:00Z`));
  const dayNumber = (dayKey: string) => dayKey.slice(8);
  const relativeDayLabel = (dayKey: string) => {
    if (dayKey === todayKey) return t("schedule.today");
    if (dayKey === addDays(todayKey, 1)) return t("schedule.tomorrow");
    if (dayKey === addDays(todayKey, -1)) return t("schedule.yesterday");
    return null;
  };

  return (
    <div className={styles.board}>
      <nav className={styles.weekNav} aria-label={t("schedule.weekdays")}>
        <Link rel="nofollow" className={styles.weekLink} href={prevWeekHref}>{t("schedule.prevWeek")}</Link>
        <span className={styles.weekRange}>
          {t("schedule.weekRange", {
            from: rangeFormatter.format(new Date(`${days[0]}T12:00:00Z`)),
            to: rangeFormatter.format(new Date(`${days[6]}T12:00:00Z`)),
          })}
        </span>
        <Link rel="nofollow" className={styles.weekLink} href={nextWeekHref}>{t("schedule.nextWeek")}</Link>
      </nav>

      <div
        className={styles.dayTabs}
        role="tablist"
        aria-label={t("schedule.weekdays")}
        onKeyDown={onTabsKeyDown}
      >
        {days.map((dayKey, index) => {
          const count = grouped.get(dayKey)?.length ?? 0;
          const isActive = dayKey === activeDay;
          return (
            <button
              className={`${styles.dayTab} ${isActive ? styles.dayTabActive : ""} ${dayKey === todayKey ? styles.dayTabToday : ""}`}
              type="button"
              role="tab"
              id={`${boardId}-tab-${dayKey}`}
              aria-selected={isActive}
              aria-controls={`${boardId}-panel`}
              // Roving tabindex: the tablist is a single tab stop and arrow keys
              // move between days, as expected for role="tablist".
              tabIndex={isActive ? 0 : -1}
              ref={(node) => { tabRefs.current[index] = node; }}
              key={dayKey}
              onClick={() => setSelectedDay(dayKey)}
            >
              <span className={styles.dayTabName}>{dayLabel(dayKey)}</span>
              <span className={styles.dayTabDate}>{dayNumber(dayKey)}</span>
              <span className={styles.dayTabCount}>{count}</span>
            </button>
          );
        })}
      </div>

      <div id={`${boardId}-panel`} role="tabpanel" aria-labelledby={`${boardId}-tab-${activeDay}`}>
      <header className={styles.dayHeading}>
        <div>
          <h2>{fullDayFormatter.format(new Date(`${activeDay}T12:00:00Z`))}</h2>
          <p className={styles.dayMeta}>
            {relativeDayLabel(activeDay) ? `${relativeDayLabel(activeDay)} · ` : ""}
            {t("schedule.episodesCount", { count: dayItems.length })}
          </p>
        </div>
        <div className={styles.dayHeadingActions}>
          {activeDay !== todayKey && days.includes(todayKey) && (
            <button className={styles.todayButton} type="button" onClick={() => setSelectedDay(todayKey)}>
              {t("schedule.today")}
            </button>
          )}
          {!days.includes(todayKey) && (
            <Link rel="nofollow" className={styles.todayButton} href={thisWeekHref}>{t("schedule.thisWeek")}</Link>
          )}
        </div>
      </header>

      {clock.local && <p className={styles.timezoneNote}>{t("schedule.timezoneNote")}</p>}

      {dayItems.length ? (
        <ul className={styles.episodes}>
          {dayItems.map((item) => {
            const status = scheduleStatus(item, clock.now, todayKey, clock.local);
            const moment = item.air_at ? new Date(item.air_at) : null;
            const hasTime = moment !== null && !Number.isNaN(moment.getTime());
            return (
              <li key={item.id}>
                <Link className={styles.episode} href={`/titles/${item.title.slug}/episodes/${item.number}`}>
                  <span className={styles.poster}>
                    {item.title.poster_url ? (
                      <Image
                        className={styles.posterImage}
                        src={item.title.poster_url}
                        alt=""
                        fill
                        sizes="72px"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <span className={styles.posterFallback} aria-hidden="true">
                        {item.title.name.slice(0, 1).toUpperCase()}
                      </span>
                    )}
                  </span>
                  <span className={styles.episodeBody}>
                    <strong className={styles.episodeTitle}>{item.title.name}</strong>
                    <span className={styles.episodeMeta}>
                      <span className={styles.number}>{t("episode.number", { number: item.number })}</span>
                      {item.name && <span className={styles.episodeName}>{item.name}</span>}
                    </span>
                  </span>
                  <span className={styles.episodeSide}>
                    {/* A known moment stays blank until the browser timezone is
                        available, so no wrong time is ever displayed. */}
                    <span className={hasTime && !clock.local ? styles.timePending : styles.time}>
                      {hasTime
                        ? (clock.local ? timeFormatter.format(moment) : "—")
                        : t("schedule.timeUnknown")}
                    </span>
                    <span className={`${styles.status} ${STATUS_CLASS[status.kind]}`}>{statusLabel(status, t)}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="empty-state" role="status">
          <strong>{t("schedule.noEpisodes")}</strong>
          <span>{t("schedule.noEpisodesText")}</span>
          <Link className="secondary" href="/catalog">{t("home.openCatalog")}</Link>
        </div>
      )}
      </div>
    </div>
  );
}
