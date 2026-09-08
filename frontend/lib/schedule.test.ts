import assert from "node:assert/strict";
import { test } from "node:test";
import type { ScheduleItem } from "./api.ts";
import {
  addDays,
  groupByDay,
  itemDayKey,
  localDayKey,
  scheduleStatus,
  weekDays,
  weekStart,
} from "./schedule.ts";

function scheduleItem(overrides: Partial<ScheduleItem> & { id: number }): ScheduleItem {
  return {
    id: overrides.id,
    number: overrides.number ?? 1,
    name: overrides.name ?? "",
    air_date: overrides.air_date ?? "2026-08-23",
    air_at: overrides.air_at ?? null,
    title: overrides.title ?? { name: "Title", slug: "title" },
  };
}

const NOW = Date.parse("2026-08-23T12:00:00Z");
const TODAY = localDayKey(new Date(NOW));

test("weekStart snaps every weekday to its Monday", () => {
  assert.equal(weekStart("2026-08-17"), "2026-08-17"); // Monday
  assert.equal(weekStart("2026-08-20"), "2026-08-17"); // Thursday
  assert.equal(weekStart("2026-08-23"), "2026-08-17"); // Sunday
  assert.deepEqual(weekDays("2026-08-17"), [
    "2026-08-17", "2026-08-18", "2026-08-19", "2026-08-20",
    "2026-08-21", "2026-08-22", "2026-08-23",
  ]);
});

test("addDays crosses month, year and leap boundaries", () => {
  assert.equal(addDays("2026-08-31", 1), "2026-09-01");
  assert.equal(addDays("2027-01-01", -1), "2026-12-31");
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
  assert.equal(addDays("2028-03-01", -1), "2028-02-29");
});

test("day grouping uses the confirmed moment only once local time is known", () => {
  // A late-night broadcast belongs to the next calendar day for the viewer.
  const lateNight = scheduleItem({ id: 1, air_date: "2026-08-23", air_at: "2026-08-24T00:30:00Z" });
  assert.equal(itemDayKey(lateNight, false), "2026-08-23");
  assert.equal(itemDayKey(lateNight, true), localDayKey(new Date("2026-08-24T00:30:00Z")));
});

test("countdown states are derived from the confirmed moment", () => {
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 2, air_date: TODAY, air_at: "2026-08-23T12:20:00Z" }), NOW, TODAY, true),
    { kind: "minutes", minutes: 20 },
  );
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 3, air_date: TODAY, air_at: "2026-08-23T15:30:00Z" }), NOW, TODAY, true),
    { kind: "hours", hours: 3, minutes: 30 },
  );
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 4, air_date: TODAY, air_at: "2026-08-23T11:50:00Z" }), NOW, TODAY, true),
    { kind: "airing" },
  );
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 5, air_date: TODAY, air_at: "2026-08-23T09:00:00Z" }), NOW, TODAY, true),
    { kind: "released" },
  );
});

test("no time is invented without a confirmed moment or a known timezone", () => {
  // Day-only episodes never claim a broadcast time.
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 6, air_date: TODAY }), NOW, TODAY, true),
    { kind: "unconfirmed" },
  );
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 7, air_date: addDays(TODAY, -1) }), NOW, TODAY, true),
    { kind: "released" },
  );
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 8, air_date: addDays(TODAY, 1) }), NOW, TODAY, true),
    { kind: "upcoming" },
  );
  // Server render: a real moment exists but cannot be resolved yet.
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 9, air_date: TODAY, air_at: "2026-08-23T12:20:00Z" }), NOW, TODAY, false),
    { kind: "pending" },
  );
  // Malformed input degrades to the day-level state instead of NaN output.
  assert.deepEqual(
    scheduleStatus(scheduleItem({ id: 10, air_date: TODAY, air_at: "nonsense" }), NOW, TODAY, true),
    { kind: "unconfirmed" },
  );
});

test("grouping orders confirmed moments ahead of day-only entries", () => {
  const grouped = groupByDay(
    [
      scheduleItem({ id: 11, number: 3, air_date: TODAY, title: { name: "B", slug: "b" } }),
      scheduleItem({ id: 12, number: 1, air_date: TODAY, air_at: new Date(`${TODAY}T21:00:00`).toISOString() }),
      scheduleItem({ id: 13, number: 2, air_date: TODAY, air_at: new Date(`${TODAY}T09:00:00`).toISOString() }),
    ],
    true,
  );
  assert.deepEqual(grouped.get(TODAY)?.map((entry) => entry.id), [13, 12, 11]);
});
