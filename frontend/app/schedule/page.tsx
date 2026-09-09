import type { Metadata } from "next";
import { ScheduleBoard } from "../../components/schedule-board";
import { PageShell } from "../../components/page-shell";
import { getSchedule } from "../../lib/api";
import { addDays, localDayKey, weekStart } from "../../lib/schedule";
import { getI18n } from "../../i18n/server";
import { NO_INDEX_ROBOTS } from "../../lib/seo";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<{ week?: string; range?: string }>;
}): Promise<Metadata> {
  const { t } = await getI18n();
  const params = await searchParams;
  const isArchiveView = Boolean(params.week || params.range);
  return {
    title: t("schedule.title"),
    description: t("schedule.subtitle"),
    alternates: { canonical: "/schedule" },
    ...(isArchiveView ? { robots: NO_INDEX_ROBOTS } : {}),
  };
}

const WEEK_KEY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

/** Validates a `week` query value and normalizes it to that week's Monday. */
function resolveWeekStart(raw: string | undefined, todayKey: string) {
  if (raw && WEEK_KEY_PATTERN.test(raw) && !Number.isNaN(Date.parse(`${raw}T00:00:00Z`))) {
    return weekStart(raw);
  }
  return weekStart(todayKey);
}

export default async function SchedulePage({
  searchParams,
}: { searchParams: Promise<{ week?: string; range?: string }> }) {
  const params = await searchParams;
  const todayKey = localDayKey(new Date());
  const startKey = resolveWeekStart(params.week, todayKey);
  const endKey = addDays(startKey, 6);
  // Neighbouring days are fetched too: a confirmed late-night `air_at` can fall
  // into the previous or next calendar day once the viewer timezone applies.
  const [schedule, { t }] = await Promise.all([
    getSchedule(addDays(startKey, -1), addDays(endKey, 1)).catch(() => null),
    getI18n(),
  ]);

  return (
    <PageShell
      active="schedule"
      heading={{ eyebrow: t("schedule.eyebrow"), title: t("schedule.title"), subtitle: t("schedule.subtitle") }}
    >
      <ScheduleBoard
        key={startKey}
        items={schedule?.results ?? []}
        unavailable={!schedule}
        weekStartKey={startKey}
        serverTodayKey={todayKey}
        prevWeekHref={`/schedule?week=${addDays(startKey, -7)}`}
        nextWeekHref={`/schedule?week=${addDays(startKey, 7)}`}
        thisWeekHref="/schedule"
      />
    </PageShell>
  );
}
