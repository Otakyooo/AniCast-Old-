import Link from "next/link";
import { AccountLink } from "../../components/account-link";
import { Sidebar } from "../../components/sidebar";
import { getSchedule, type ScheduleItem } from "../../lib/api";
import { getI18n } from "../../i18n/server";
import styles from "./schedule.module.css";

export const dynamic = "force-dynamic";

type Range = "today" | "week";

function dateString(date: Date) {
  return date.toISOString().slice(0, 10);
}

function formatDay(value: string, locale: string) {
  return new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

export default async function SchedulePage({ searchParams }: { searchParams: Promise<{ range?: string }> }) {
  const params = await searchParams;
  const range: Range = params.range === "today" ? "today" : "week";
  const start = new Date();
  start.setUTCHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + (range === "today" ? 0 : 6));
  const schedule = await getSchedule(dateString(start), dateString(end));
  const { t, locale } = await getI18n();
  const grouped = new Map<string, ScheduleItem[]>();
  for (const episode of schedule.results) grouped.set(episode.air_date, [...(grouped.get(episode.air_date) ?? []), episode]);

  return <main className="shell"><Sidebar active="schedule" /><section className="content"><header className="topbar"><span className="eyebrow">{t("schedule.eyebrow")}</span><AccountLink /></header><div className="page-heading"><h1>{t("schedule.title")}</h1><p className="muted">{t("schedule.subtitle")}</p></div><nav className={styles.range}><Link href="/schedule?range=today">{t("schedule.today")}</Link><Link href="/schedule?range=week">{t("schedule.week")}</Link></nav>{grouped.size ? <div className={styles.days}>{[...grouped.entries()].map(([date, episodes]) => <section className={styles.day} key={date}><header className={styles.dayHeading}><h2>{formatDay(date, locale)}</h2><p>{date}</p></header><div className={styles.episodes}>{episodes.map((episode) => <Link className={styles.episode} href={`/titles/${episode.title.slug}/episodes/${episode.number}`} key={episode.id}><strong>{episode.title.name}</strong><span className={styles.number}>{t("episode.number", { number: episode.number })}</span><span>{episode.name || t("episode.untitled")}</span>{episode.synopsis && <small>{episode.synopsis}</small>}</Link>)}</div></section>)}</div> : <div className="empty-state"><strong>{t("schedule.empty")}</strong><span>{t("schedule.emptyText")}</span><Link href="/catalog">{t("home.openCatalog")}</Link></div>}</section></main>;
}
