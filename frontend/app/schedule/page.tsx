import Link from "next/link";
import { AccountLink } from "../../components/account-link";
import { Sidebar } from "../../components/sidebar";
import { getSchedule, type ScheduleItem } from "../../lib/api";
import styles from "./schedule.module.css";

export const dynamic = "force-dynamic";

type Range = "today" | "week";

function dateString(date: Date) {
  return date.toISOString().slice(0, 10);
}

function formatDay(value: string) {
  return new Intl.DateTimeFormat("ru-RU", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}

export default async function SchedulePage({ searchParams }: { searchParams: Promise<{ range?: string }> }) {
  const params = await searchParams;
  const range: Range = params.range === "today" ? "today" : "week";
  const start = new Date();
  start.setUTCHours(0, 0, 0, 0);
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + (range === "today" ? 0 : 6));
  const schedule = await getSchedule(dateString(start), dateString(end));
  const grouped = new Map<string, ScheduleItem[]>();
  for (const episode of schedule.results) grouped.set(episode.air_date, [...(grouped.get(episode.air_date) ?? []), episode]);

  return <main className="shell"><Sidebar active="schedule" /><section className="content"><header className="topbar"><span className="eyebrow">КАЛЕНДАРЬ РЕЛИЗОВ</span><AccountLink /></header><div className="page-heading"><h1>Расписание</h1><p className="muted">Подтверждённые даты эпизодов без выдуманного времени выхода.</p></div><nav className={styles.range} aria-label="Диапазон расписания"><Link href="/schedule?range=today">Сегодня</Link><Link href="/schedule?range=week">7 дней</Link></nav>{grouped.size ? <div className={styles.days}>{[...grouped.entries()].map(([date, episodes]) => <section className={styles.day} key={date}><header className={styles.dayHeading}><h2>{formatDay(date)}</h2><p>{date}</p></header><div className={styles.episodes}>{episodes.map((episode) => <Link className={styles.episode} href={`/titles/${episode.title.slug}/episodes/${episode.number}`} key={episode.id}><strong>{episode.title.name}</strong><span className={styles.number}>Эпизод {episode.number}</span><span>{episode.name || "Без названия"}</span>{episode.synopsis && <small>{episode.synopsis}</small>}</Link>)}</div></section>)}</div> : <div className="empty-state"><strong>На выбранный период релизов нет</strong><span>Здесь появляются только эпизоды с подтверждённой датой выхода.</span><Link href="/catalog">Открыть каталог</Link></div>}</section></main>;
}
