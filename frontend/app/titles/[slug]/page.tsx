import Link from "next/link";
import { AccountLink } from "../../../components/account-link";
import { LibraryControl } from "../../../components/library-control";
import { Sidebar } from "../../../components/sidebar";
import { getCatalogItem, type Episode, type Source } from "../../../lib/api";

export const dynamic = "force-dynamic";

const availabilityLabels: Record<string, string> = {
  available: "Доступен",
  unavailable: "Недоступен",
  geo_blocked: "Заблокирован в регионе",
  expired: "Срок действия истёк",
  provider_error: "Ошибка провайдера",
};

function availabilityLabel(source: Source) {
  return availabilityLabels[source.availability] ?? source.availability;
}

function SourceStatus({ source }: { source: Source }) {
  return (
    <li className={`source-status source-status-${source.availability}`}>
      <span className="source-status-main">
        <strong>{source.name}</strong>
        <span>{source.kind.toUpperCase()}</span>
      </span>
      <span className="source-status-label">{availabilityLabel(source)}</span>
      {source.availability_reason && <small>{source.availability_reason}</small>}
    </li>
  );
}

function EpisodeCard({ episode, slug }: { episode: Episode; slug: string }) {
  const sources = episode.sources ?? [];

  return (
    <li className="episode-card">
      <div className="episode-heading">
        <span className="episode-number">Эпизод {episode.number}</span>
        <strong>{episode.name || "Без названия"}</strong>
        {episode.air_date && <time dateTime={episode.air_date}>{episode.air_date}</time>}
      </div>
      {episode.synopsis && <p className="muted">{episode.synopsis}</p>}
      <Link className="secondary" href={`/titles/${slug}/episodes/${episode.number}`}>Открыть эпизод</Link>
      <div className="episode-sources">
        <h3>Источники</h3>
        {sources.length ? (
          <ul className="source-list">
            {sources.map((source) => <SourceStatus key={`${source.name}-${source.kind}`} source={source} />)}
          </ul>
        ) : (
          <p className="muted">Источники пока не добавлены.</p>
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

  return (
    <main className="shell">
      <Sidebar active="catalog" />
      <section className="content">
        <header className="topbar">
          <Link className="back-link" href="/catalog">← Каталог</Link>
          <AccountLink />
        </header>
        <article className="detail">
          <div className="detail-poster poster-placeholder" style={{ "--poster-accent": "#6d5dfb" } as React.CSSProperties} aria-label={`Обложка: ${item.name}`}>
            <span>{item.name.slice(0, 1).toUpperCase()}</span>
          </div>
          <div className="detail-copy">
            <p className="eyebrow">{item.title_type ?? "АНИМЕ"}</p>
            <h1>{item.name}</h1>
            {item.original_name && <p className="original-title">{item.original_name}</p>}
            <p className="muted">{item.synopsis || "Описание для этого тайтла пока не добавлено."}</p>
            <div className="detail-meta">
              <span>{item.year ?? "Год неизвестен"}</span>
              <span>{episodes.length ? `${episodes.length} эп.` : "Эпизоды уточняются"}</span>
              <span>{item.status ?? "Статус уточняется"}</span>
            </div>
            {genres.length > 0 && <div className="tag-list">{genres.map((genre) => <span key={genre.slug}>{genre.name}</span>)}</div>}
            <LibraryControl slug={item.slug} />
            {item.franchise && <section className="franchise-panel"><p className="eyebrow">ФРАНШИЗА</p><h2>{item.franchise.name}</h2>{item.franchise.description && <p className="muted">{item.franchise.description}</p>}</section>}
          </div>
        </article>
        <section className="episodes-section" aria-labelledby="episodes-heading">
          <div className="section-heading"><p className="eyebrow">ПРОСМОТР</p><h2 id="episodes-heading">Эпизоды</h2></div>
          {episodes.length ? <ol className="episode-list">{episodes.map((episode) => <EpisodeCard key={episode.number} episode={episode} slug={item.slug} />)}</ol> : <div className="empty-state"><strong>Эпизоды пока не добавлены</strong><span>Мы уточняем данные для этого тайтла.</span></div>}
        </section>
      </section>
    </main>
  );
}

function NotFoundState() {
  return <main className="shell"><section className="content"><div className="state-panel" role="status"><p className="eyebrow">404</p><h1>Тайтл не найден</h1><p className="muted">Похоже, этот тайтл ещё не появился в каталоге или был перемещён.</p><Link className="primary inline-button" href="/catalog">Вернуться в каталог</Link></div></section></main>;
}
