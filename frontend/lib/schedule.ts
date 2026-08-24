import type { ScheduleItem } from "./api";

export const MINUTE_MS = 60_000;
export const HOUR_MS = 60 * MINUTE_MS;
/** How long after `air_at` an episode is still reported as airing right now. */
export const AIRING_WINDOW_MS = 30 * MINUTE_MS;

/**
 * Release state of one scheduled episode.
 *
 * `unconfirmed` is used when only the calendar day is known: the backend never
 * invents a broadcast time, so neither does the UI. `pending` marks a confirmed
 * moment that cannot be resolved yet because the viewer timezone is unknown
 * during the server render and the first client paint.
 */
export type ScheduleStatus =
  | { kind: "released" }
  | { kind: "airing" }
  | { kind: "minutes"; minutes: number }
  | { kind: "hours"; hours: number; minutes: number }
  | { kind: "upcoming" }
  | { kind: "pending" }
  | { kind: "unconfirmed" };

/** Calendar day of a Date in the runtime timezone, as YYYY-MM-DD. */
export function localDayKey(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/** Shifts a YYYY-MM-DD key by whole days without DST drift. */
export function addDays(dayKey: string, days: number): string {
  const anchor = new Date(`${dayKey}T12:00:00Z`);
  anchor.setUTCDate(anchor.getUTCDate() + days);
  return anchor.toISOString().slice(0, 10);
}

/** Monday of the week containing `dayKey` (ISO week convention). */
export function weekStart(dayKey: string): string {
  const anchor = new Date(`${dayKey}T12:00:00Z`);
  const weekday = anchor.getUTCDay();
  return addDays(dayKey, weekday === 0 ? -6 : 1 - weekday);
}

/** The seven day keys of the week beginning at `startDayKey`. */
export function weekDays(startDayKey: string): string[] {
  return Array.from({ length: 7 }, (_, index) => addDays(startDayKey, index));
}

/**
 * Day the episode belongs to.
 *
 * Before hydration only `air_date` is available in a timezone-independent way,
 * so `useLocalTime` stays false and the server-confirmed day is used. Once the
 * browser timezone is known, a confirmed `air_at` decides the day, which can
 * differ from `air_date` for late-night broadcasts.
 */
export function itemDayKey(item: ScheduleItem, useLocalTime: boolean): string {
  if (useLocalTime && item.air_at) {
    const moment = new Date(item.air_at);
    if (!Number.isNaN(moment.getTime())) return localDayKey(moment);
  }
  return item.air_date;
}

export function scheduleStatus(
  item: ScheduleItem,
  nowMs: number,
  todayKey: string,
  useLocalTime: boolean,
): ScheduleStatus {
  const moment = item.air_at ? new Date(item.air_at) : null;
  const hasMoment = moment !== null && !Number.isNaN(moment.getTime());
  // Before the viewer timezone is known there is no honest "now" to compare
  // against, so only the day-level state is reported. A countdown derived from
  // the server day boundary would be wrong by up to a full day.
  if (!useLocalTime || !hasMoment) {
    const dayKey = itemDayKey(item, useLocalTime);
    if (dayKey < todayKey) return { kind: "released" };
    if (dayKey > todayKey) return { kind: "upcoming" };
    return hasMoment ? { kind: "pending" } : { kind: "unconfirmed" };
  }
  const diff = moment.getTime() - nowMs;
  if (diff <= -AIRING_WINDOW_MS) return { kind: "released" };
  if (diff <= 0) return { kind: "airing" };
  if (diff < HOUR_MS) return { kind: "minutes", minutes: Math.max(1, Math.ceil(diff / MINUTE_MS)) };
  if (diff < 24 * HOUR_MS) {
    const hours = Math.floor(diff / HOUR_MS);
    return { kind: "hours", hours, minutes: Math.floor((diff - hours * HOUR_MS) / MINUTE_MS) };
  }
  return { kind: "upcoming" };
}

/** Groups episodes by their day, preserving the backend ordering inside a day. */
export function groupByDay(items: ScheduleItem[], useLocalTime: boolean): Map<string, ScheduleItem[]> {
  const grouped = new Map<string, ScheduleItem[]>();
  for (const item of items) {
    const key = itemDayKey(item, useLocalTime);
    const bucket = grouped.get(key);
    if (bucket) bucket.push(item);
    else grouped.set(key, [item]);
  }
  if (!useLocalTime) return grouped;
  for (const bucket of grouped.values()) {
    bucket.sort((left, right) => {
      if (left.air_at && right.air_at) return left.air_at.localeCompare(right.air_at);
      if (left.air_at) return -1;
      if (right.air_at) return 1;
      return left.title.name.localeCompare(right.title.name) || left.number - right.number;
    });
  }
  return grouped;
}
