import { notFound } from "next/navigation";
import { EpisodeProgressControl } from "../../../../../components/episode-progress-control";
import { ApiUnavailableState } from "../../../../../components/api-unavailable";
import { PageShell } from "../../../../../components/page-shell";
import { SourceReportControl } from "../../../../../components/source-report-control";
import { PlaybackLink } from "../../../../../components/playback-link";
import { apiErrorStatus, getEpisode } from "../../../../../lib/api";
import { getI18n } from "../../../../../i18n/server";
import styles from "../../../../history.module.css";

export const dynamic = "force-dynamic";

export default async function EpisodePage({ params }: { params: Promise<{ slug: string; number: string }> }) {
  const { slug, number: rawNumber } = await params;
  const number = Number(rawNumber);
  if (!Number.isInteger(number) || number < 1) notFound();
  const { t } = await getI18n();
  let episode;
  try { episode = await getEpisode(slug, number); }
  catch (error) { if (apiErrorStatus(error) === 404) notFound(); return <ApiUnavailableState />; }
  const sources = episode.sources ?? [];
  const sourceLabel = (value: string) => t(`source.${value === "geo_blocked" ? "geo" : value === "provider_error" ? "error" : value}`);

  return <PageShell active="catalog" back={{ href: `/titles/${episode.title.slug}`, label: episode.title.name }}>
    <article className={styles.episodePage}>
      <p className="eyebrow">{t("episode.number", { number: episode.number })}</p>
      <h1>{episode.name || episode.title.name}</h1>
      <p className="muted">{episode.synopsis || t("episode.noDescription")}</p>
      <EpisodeProgressControl slug={episode.title.slug} number={episode.number} />
      <section className="section">
        <div className="section-heading"><h2>{t("episode.sources")}</h2></div>
        {sources.length ? (
          <ul className={styles.sources}>
            {sources.map((source) => (
              <li className={styles.source} key={source.id}>
                <strong>{source.name}</strong>
                <span>{source.kind.toUpperCase()} · {sourceLabel(source.availability)}</span>
                {source.availability_reason && <small>{source.availability_reason}</small>}
                {source.playback_available && <PlaybackLink sourceId={source.id} playbackMode={source.playback_mode} />}
                <SourceReportControl sourceId={source.id} />
              </li>
            ))}
          </ul>
        ) : (
          <div className="empty-state"><strong>{t("episode.noSources")}</strong></div>
        )}
      </section>
    </article>
  </PageShell>;
}
