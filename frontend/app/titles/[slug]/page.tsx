import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageShell } from "../../../components/page-shell";
import { TitleActions } from "../../../components/title-actions";
import { TitleNoteControl } from "../../../components/title-note-control";
import { NotificationSubscription } from "../../../components/notification-subscription";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { CommunityPanel } from "../../../components/community-panel";
import { TitleCollectionControl } from "../../../components/title-collection-control";
import { CatalogCard } from "../../../components/catalog-card";
import {
  apiErrorStatus,
  getCatalogItem,
  getCatalogItemEpisodes,
  getFirstEpisodeNumber,
  getSimilarTitles,
  type CatalogItem,
  type Episode,
  type Source,
  type TitleCastEntry,
} from "../../../lib/api";
import { absoluteUrl, metaDescription } from "../../../lib/site";
import { getI18n } from "../../../i18n/server";
import styles from "../title.module.css";

export const dynamic = "force-dynamic";

type Translator = (key: string, values?: Record<string, string | number>) => string;

const TABS = ["overview", "episodes", "characters", "community", "notes"] as const;
type Tab = typeof TABS[number];

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const { t } = await getI18n();
  let item: CatalogItem;
  try {
    item = await getCatalogItem(slug);
  } catch (error) {
    if (apiErrorStatus(error) === 404) notFound();
    // Degraded API still needs sane metadata; the page itself shows the
    // unavailable state.
    return { title: "AniCast", description: t("meta.description") };
  }

  const description = metaDescription(item.synopsis, t("meta.description"));
  return {
    title: item.name,
    description,
    alternates: { canonical: `/titles/${item.slug}` },
    openGraph: {
      type: "video.tv_show",
      url: `/titles/${item.slug}`,
      siteName: "AniCast",
      title: item.name,
      description,
      ...(item.poster_url ? { images: [{ url: absoluteUrl(item.poster_url), alt: item.name }] } : {}),
    },
    twitter: {
      card: item.poster_url ? "summary_large_image" : "summary",
      title: item.name,
      description,
    },
  };
}

/** schema.org TVSeries payload for rich search results. */
function TitleJsonLd({ item }: { item: CatalogItem }) {
  const data: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "TVSeries",
    name: item.name,
    url: absoluteUrl(`/titles/${item.slug}`),
  };
  if (item.original_name) data.alternateName = item.original_name;
  if (item.synopsis) data.description = metaDescription(item.synopsis, "", 5000);
  if (item.poster_url) data.image = absoluteUrl(item.poster_url);
  if (item.year) data.datePublished = String(item.year);
  if (item.genres?.length) data.genre = item.genres.map((genre) => genre.name);
  if (item.episodes_count) data.numberOfEpisodes = item.episodes_count;
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}

function isTab(value: string | undefined): value is Tab {
  return TABS.includes((value ?? "") as Tab);
}

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
        {episode.air_date && <time dateTime={episode.air_at ?? episode.air_date}>{episode.air_date}</time>}
      </div>
      {episode.synopsis && <p className="muted">{episode.synopsis}</p>}
      <Link className="secondary" href={`/titles/${slug}/watch?episode=${episode.number}`}>{t("watch.title")}</Link>
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

function CastCard({ entry, t }: { entry: TitleCastEntry; t: Translator }) {
  const { character } = entry;
  return (
    <Link className={styles.castCard} href={`/characters/${character.slug}`}>
      <span className={styles.castAvatar}>
        {character.image_url ? (
          <Image
            className={styles.castImage}
            src={character.image_url}
            alt=""
            fill
            sizes="96px"
            referrerPolicy="no-referrer"
          />
        ) : (
          <span aria-hidden="true">{character.name.slice(0, 1).toUpperCase()}</span>
        )}
      </span>
      <span className={styles.castBody}>
        <strong>{character.name}</strong>
        <small>{t(`role.${entry.role}`)}</small>
      </span>
    </Link>
  );
}

export default async function CatalogDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ episodes_page?: string; tab?: string }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const rawPage = Number(query.episodes_page);
  const requestedPage = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  // An existing `?episodes_page=` link must still land on the episode list, so
  // pagination implies the episodes tab when no explicit tab is requested.
  const tab: Tab = isTab(query.tab) ? query.tab : query.episodes_page ? "episodes" : "overview";

  let item;
  let episodesPage = requestedPage;
  try {
    item = await getCatalogItemEpisodes(slug, requestedPage);
  } catch (error) {
    if (apiErrorStatus(error) !== 404) return <ApiUnavailableState />;
    // The API answers 404 both for a missing title and for an episode page past
    // the end. Retry the first page so an existing title still renders instead
    // of claiming the title does not exist.
    if (requestedPage === 1) notFound();
    try {
      item = await getCatalogItemEpisodes(slug, 1);
      episodesPage = 1;
    } catch (retryError) {
      if (apiErrorStatus(retryError) === 404) notFound();
      return <ApiUnavailableState />;
    }
  }

  const episodes = item.episodes ?? [];
  const episodesCount = item.episodes_count ?? episodes.length;
  const pageCount = Math.max(1, Math.ceil(episodesCount / 20));
  const genres = item.genres ?? [];
  const cast = item.characters ?? [];
  // Main cast for the overview: heroes and antagonists only — supporting and
  // cameo entries stay on the characters tab. Voice actors are not part of
  // the dataset at all.
  const mainCast = cast
    .filter((entry) => entry.role === "protagonist" || entry.role === "antagonist")
    .slice(0, 8);
  const [similar, firstEpisode] = await Promise.all([
    tab === "overview" ? getSimilarTitles(slug) : Promise.resolve([]),
    // The hero action must point at the real first episode regardless of which
    // episode page the viewer is on, so it is resolved independently.
    episodesPage === 1 && episodes.length
      ? Promise.resolve(Math.min(...episodes.map((episode) => episode.number)))
      : getFirstEpisodeNumber(slug),
  ]);
  const { t } = await getI18n();

  const tabHref = (value: Tab) => value === "overview" ? `/titles/${item.slug}` : `/titles/${item.slug}?tab=${value}`;
  const tabLabel: Record<Tab, string> = {
    overview: t("title.tabOverview"),
    episodes: t("title.tabEpisodes"),
    characters: t("title.tabCharacters"),
    community: t("title.tabCommunity"),
    notes: t("title.tabNotes"),
  };

  return (
    <PageShell active="catalog" back={{ href: "/catalog", label: t("catalog.title") }}>
      <TitleJsonLd item={item} />
      <article className={styles.hero}>
        <div className={styles.heroPoster}>
          {item.poster_url ? (
            <Image
              className={styles.heroImage}
              src={item.poster_url}
              alt={t("title.cover", { name: item.name })}
              fill
              sizes="(max-width: 767px) 45vw, 280px"
              referrerPolicy="no-referrer"
              priority
            />
          ) : (
            <span className={styles.heroPosterFallback} aria-hidden="true">
              {item.name.slice(0, 1).toUpperCase()}
            </span>
          )}
        </div>
        <div className={styles.heroCopy}>
          <p className="eyebrow">{t(`type.${item.title_type ?? "anime"}`)}</p>
          <h1 className={styles.heroTitle}>{item.name}</h1>
          {item.original_name && <p className={styles.heroOriginal}>{item.original_name}</p>}
          <div className={styles.heroMeta}>
            <span className={item.status === "ongoing" ? styles.metaOngoing : undefined}>
              {item.status ? t(`status.${item.status}`) : t("status.unknown")}
            </span>
            <span>{item.year ?? t("title.yearUnknown")}</span>
            <span>{episodesCount ? t("title.episodesCount", { count: episodesCount }) : t("title.episodesUnknown")}</span>
          </div>
          {genres.length > 0 && (
            <div className={styles.heroGenres}>
              {genres.map((genre) => (
                <Link href={`/catalog?genre=${encodeURIComponent(genre.slug)}`} key={genre.slug}>{genre.name}</Link>
              ))}
            </div>
          )}
        </div>
        <TitleActions slug={item.slug} firstEpisode={firstEpisode} />
      </article>

      <nav className={styles.tabs} aria-label={t("title.tabOverview")}>
        {TABS.map((value) => (
          <Link
            className={`${styles.tab} ${value === tab ? styles.tabActive : ""}`}
            href={tabHref(value)}
            aria-current={value === tab ? "page" : undefined}
            key={value}
          >
            {tabLabel[value]}
            {value === "episodes" && episodesCount > 0 && <span className={styles.tabCount}>{episodesCount}</span>}
            {value === "characters" && cast.length > 0 && <span className={styles.tabCount}>{cast.length}</span>}
          </Link>
        ))}
      </nav>

      {tab === "overview" && (
        <div className={styles.panel}>
          <section className={styles.block}>
            <h2>{t("title.description")}</h2>
            <p className="muted">{item.synopsis || t("title.descriptionMissing")}</p>
          </section>
          <section className={styles.block}>
            <h2>{t("title.details")}</h2>
            <dl className={styles.detailsList}>
              <div><dt>{t("catalog.format")}</dt><dd>{t(`type.${item.title_type ?? "anime"}`)}</dd></div>
              <div><dt>{t("catalog.status")}</dt><dd>{item.status ? t(`status.${item.status}`) : t("status.unknown")}</dd></div>
              <div><dt>{t("title.episodes")}</dt><dd>{episodesCount || t("title.episodesUnknown")}</dd></div>
              <div><dt>{t("title.genres")}</dt><dd>{genres.length ? genres.map((genre) => genre.name).join(", ") : t("title.noGenres")}</dd></div>
            </dl>
          </section>
          {mainCast.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("title.castMain")}</h2>
                {cast.length > mainCast.length && (
                  <Link href={`/titles/${item.slug}?tab=characters`}>{t("title.castAll")} ({cast.length})</Link>
                )}
              </div>
              <div className={styles.castGrid}>
                {mainCast.map((entry) => <CastCard entry={entry} key={entry.character.slug} t={t} />)}
              </div>
            </section>
          )}
          {item.franchise && (
            <Link className="franchise-panel" href={`/franchises/${item.franchise.slug}`}>
              <p className="eyebrow">{t("franchise.label")}</p>
              <h2>{item.franchise.name}</h2>
              {item.franchise.description && <p className="muted">{item.franchise.description}</p>}
            </Link>
          )}
          <NotificationSubscription slug={item.slug} />
          <TitleCollectionControl titleSlug={item.slug} />
          {similar.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("similar.title")}</h2>
                <Link href="/catalog">{t("home.allCatalog")}</Link>
              </div>
              <div className="catalog-grid">{similar.map((entry) => <CatalogCard key={entry.slug} item={entry} />)}</div>
            </section>
          )}
        </div>
      )}

      {tab === "episodes" && (
        <div className={styles.panel}>
          {episodes.length ? (
            <ol className="episode-list">
              {episodes.map((episode) => <EpisodeCard key={episode.number} episode={episode} slug={item.slug} t={t} />)}
            </ol>
          ) : (
            <div className="empty-state" role="status">
              <strong>{t("title.noEpisodes")}</strong>
              <span>{t("title.noEpisodesText")}</span>
            </div>
          )}
          {pageCount > 1 && (
            <nav className="episode-pagination" aria-label={t("title.episodes")}>
              {episodesPage > 1 && (
                <Link className="secondary" href={`/titles/${item.slug}?tab=episodes&episodes_page=${episodesPage - 1}`}>
                  {t("common.back")}
                </Link>
              )}
              <span>{t("catalog.page", { current: episodesPage, total: pageCount })}</span>
              {episodesPage < pageCount && (
                <Link className="secondary" href={`/titles/${item.slug}?tab=episodes&episodes_page=${episodesPage + 1}`}>
                  {t("common.next")}
                </Link>
              )}
            </nav>
          )}
        </div>
      )}

      {tab === "characters" && (
        <div className={styles.panel}>
          {cast.length ? (
            <div className={styles.castGrid}>
              {cast.map((entry) => <CastCard entry={entry} key={entry.character.slug} t={t} />)}
            </div>
          ) : (
            <div className="empty-state" role="status">
              <strong>{t("title.noCast")}</strong>
              <Link className="secondary" href="/characters">{t("character.title")}</Link>
            </div>
          )}
        </div>
      )}

      {tab === "community" && <div className={styles.panel}><CommunityPanel slug={item.slug} /></div>}

      {tab === "notes" && <div className={styles.panel}><TitleNoteControl slug={item.slug} /></div>}
    </PageShell>
  );
}
