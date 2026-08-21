import Link from "next/link";
import { notFound } from "next/navigation";
import { AccountLink } from "../../../../../components/account-link";
import { EpisodeProgressControl } from "../../../../../components/episode-progress-control";
import { Sidebar } from "../../../../../components/sidebar";
import { SourceReportControl } from "../../../../../components/source-report-control";
import { getCatalogItem } from "../../../../../lib/api";
import styles from "../../../../history.module.css";

const availabilityLabels: Record<string, string> = { available: "Доступен", unavailable: "Недоступен", geo_blocked: "Недоступен в регионе", expired: "Срок истёк", provider_error: "Ошибка провайдера" };

export default async function EpisodePage({ params }: { params: Promise<{ slug: string; number: string }> }) {
  const { slug, number: rawNumber } = await params;
  const number = Number(rawNumber);
  if (!Number.isInteger(number) || number < 1) notFound();
  let title;
  try { title = await getCatalogItem(slug); } catch { notFound(); }
  const episode = title.episodes?.find((candidate) => candidate.number === number);
  if (!episode) notFound();
  const sources = episode.sources ?? [];

  return <main className="shell"><Sidebar active="catalog" /><section className="content"><header className="topbar"><Link className="back-link" href={`/titles/${title.slug}`}>← {title.name}</Link><AccountLink /></header><article className={styles.episodePage}><p className="eyebrow">ЭПИЗОД {episode.number}</p><h1>{episode.name || title.name}</h1><p className="muted">{episode.synopsis || "Описание эпизода пока не добавлено."}</p><EpisodeProgressControl slug={title.slug} number={episode.number} /><section><div className="section-heading"><h2>Источники</h2></div>{sources.length ? <ul className={styles.sources}>{sources.map((source) => <li className={styles.source} key={source.id}><strong>{source.name}</strong><span>{source.kind.toUpperCase()} · {availabilityLabels[source.availability] ?? source.availability}</span>{source.availability_reason && <small>{source.availability_reason}</small>}<SourceReportControl sourceId={source.id} /></li>)}</ul> : <div className="empty-state"><strong>Источники пока не добавлены</strong></div>}</section></article></section></main>;
}
