import Link from "next/link";
import { AccountLink } from "../../../components/account-link";
import { LibraryControl } from "../../../components/library-control";
import { Sidebar } from "../../../components/sidebar";
import { TitleNoteControl } from "../../../components/title-note-control";
import { NotificationSubscription } from "../../../components/notification-subscription";
import { CommunityPanel } from "../../../components/community-panel";
import { getCatalogItem, type Episode, type Source } from "../../../lib/api";
import { getI18n } from "../../../i18n/server";

export const dynamic = "force-dynamic";

type Translator = (key: string, values?: Record<string, string | number>) => string;

function SourceStatus({ source, t }: { source: Source; t: Translator }) {
  return (
    <li className={`source-status source-status-${source.availability}`}>
      <span className="source-status-main">
        <strong>{source.name}</strong>
        <span>{source.kind.toUpperCase()}</span>
      </span>
      <span className="source-status-label">{t(`source.${source.availability === "geo_blocked" ? "geo" : source.availability === "provider_error" ? "error" : source.availability}`)}</span>
      {source.availability_reason && <small>{source.availability_reason}</small>}
    </li>
  );
}

function EpisodeCard({ episode, slug, t }: { episode: Episode; slug: string; t: Translator }) {
  const sources = episode.sources ?? [];

  return (
    <li className="episode-card">
      <div className="episode-heading">
        <span className="episode-number">{t("episode.number", { number: episode.number })}</span>
        <strong>{episode.name || t("episode.untitled")}</strong>
        {episode.air_date && <time dateTime={episode.air_date}>{episode.air_date}</time>}
      </div>
      {episode.synopsis && <p className="muted">{episode.synopsis}</p>}
      <Link className="secondary" href={`/titles/${slug}/episodes/${episode.number}`}>{t("episode.open")}</Link>
      <div className="episode-sources">
        <h3>{t("episode.sources")}</h3>
        {sources.length ? (
          <ul className="source-list">
            {sources.map((source) => <SourceStatus key={`${source.name}-${source.kind}`} source={source} t={t} />)}
          </ul>
        ) : (
          <p className="muted">{t("episode.noSources")}</p>
        )}
      </div>
    </li>
  );
}

export default async function CatalogDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let item;
  try {
    item = await getCatalogItem(slug);
  } catch (error) {
    if (error instanceof Error && Object.hasOwn(error, "status") && (error as Error & { status?: number }).status === 404) return <NotFoundState />;
    throw error;
  }

  const episodes = item.episodes ?? [];
  const genres = item.genres ?? [];
  const { t } = await getI18n();

  return (
    <main className="shell">
      <Sidebar active="catalog" />
      <section className="content">
        <header className="topbar">
          <Link className="back-link" href="/catalog">← {t("catalog.title")}</Link>
          <AccountLink />
        </header>
        <article className="detail">
          <div className="detail-poster poster-placeholder" style={{ "--poster-accent": "#6d5dfb" } as React.CSSProperties} aria-label={t("title.cover", { name: item.name })}>
            <span>{item.name.slice(0, 1).toUpperCase()}</span>
          </div>
          <div className="detail-copy">
            <p className="eyebrow">{t(`type.${item.title_type ?? "anime"}`)}</p>
            <h1>{item.name}</h1>
            {item.original_name && <p className="original-title">{item.original_name}</p>}
            <p className="muted">{item.synopsis || t("title.descriptionMissing")}</p>
            <div className="detail-meta">
              <span>{item.year ?? t("title.yearUnknown")}</span>
              <span>{episodes.length ? t("title.episodesCount", { count: episodes.length }) : t("title.episodesUnknown")}</span>
              <span>{item.status ? t(`status.${item.status}`) : t("status.unknown")}</span>
            </div>
            {genres.length > 0 && <div className="tag-list">{genres.map((genre) => <span key={genre.slug}>{genre.name}</span>)}</div>}
            <LibraryControl slug={item.slug} />
            <NotificationSubscription slug={item.slug} />
            <TitleNoteControl slug={item.slug} />
            <CommunityPanel slug={item.slug} />
            {item.franchise && <Link className="franchise-panel" href={`/franchises/${item.franchise.slug}`}><p className="eyebrow">{t("franchise.label")}</p><h2>{item.franchise.name}</h2>{item.franchise.description && <p className="muted">{item.franchise.description}</p>}</Link>}
          </div>
        </article>
        <section className="episodes-section" aria-labelledby="episodes-heading">
          <div className="section-heading"><p className="eyebrow">{t("title.watch")}</p><h2 id="episodes-heading">{t("title.episodes")}</h2></div>
          {episodes.length ? <ol className="episode-list">{episodes.map((episode) => <EpisodeCard key={episode.number} episode={episode} slug={item.slug} t={t} />)}</ol> : <div className="empty-state"><strong>{t("title.noEpisodes")}</strong><span>{t("title.noEpisodesText")}</span></div>}
        </section>
      </section>
    </main>
  );
}

async function NotFoundState() {
  const { t } = await getI18n();
  return <main className="shell"><section className="content"><div className="state-panel" role="status"><p className="eyebrow">404</p><h1>{t("title.notFound")}</h1><p className="muted">{t("title.notFoundText")}</p><Link className="primary inline-button" href="/catalog">{t("title.backCatalog")}</Link></div></section></main>;
}
