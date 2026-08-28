import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PageShell } from "../../../components/page-shell";
import { CharacterAvatar } from "../../../components/character-avatar";
import { TitleActions } from "../../../components/title-actions";
import { TitleNoteControl } from "../../../components/title-note-control";
import { NotificationSubscription } from "../../../components/notification-subscription";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { BreadcrumbsJsonLd } from "../../../components/breadcrumbs-jsonld";
import { ShareButton } from "../../../components/share-button";
import { CommunityPanel } from "../../../components/community-panel";
import { TitleCollectionControl } from "../../../components/title-collection-control";
import { CatalogCard } from "../../../components/catalog-card";
import { WatchSpace } from "../../../components/watch-space";
import {
  apiErrorStatus,
  getCatalogItem,
  getCatalogItemEpisodes,
  getEpisode,
  getFirstEpisodeNumber,
  getSimilarTitles,
  getWatchNavigation,
  type CatalogItem,
  type Episode,
  type Source,
  type TitleCastEntry,
  type WatchNavigation,
} from "../../../lib/api";
import { absoluteUrl, metaDescription } from "../../../lib/site";
import { titleRating } from "../../../lib/rating";
import { titleSchemaType } from "../../../lib/seo";
import { getI18n } from "../../../i18n/server";
import { intlLocale } from "../../../i18n/config";
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
    // Degraded API still needs sane metadata; the page itself shows the
    // unavailable state. The page component owns the 404: notFound() inside
    // generateMetadata races the render and can answer 200.
    if (apiErrorStatus(error) === 404) return { title: t("title.notFound") };
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
    "@type": titleSchemaType(item.title_type),
    name: item.name,
    url: absoluteUrl(`/titles/${item.slug}`),
  };
  const alternateNames = Object.values(item.localized_names ?? {}).filter((name) => name && name !== item.name);
  if (alternateNames.length) data.alternateName = alternateNames;
  if (item.synopsis) data.description = metaDescription(item.synopsis, "", 5000);
  if (item.poster_url) data.image = absoluteUrl(item.poster_url);
  if (item.year) data.datePublished = String(item.year);
  if (item.genres?.length) data.genre = item.genres.map((genre) => genre.name);
  if (item.episodes_count) data.numberOfEpisodes = item.episodes_count;
  if (item.rating_average && item.rating_count) {
    data.aggregateRating = {
      "@type": "AggregateRating",
      ratingValue: item.rating_average,
      ratingCount: item.rating_count,
      bestRating: 10,
      worstRating: 1,
    };
  }
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}

function isTab(value: string | undefined): value is Tab {
  return TABS.includes((value ?? "") as Tab);
}

/** Noon-UTC anchor so a plain YYYY-MM-DD renders the same day in every timezone. */
function isoDay(value: string): Date {
  return new Date(`${value}T12:00:00Z`);
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

function EpisodeCard({
  episode,
  slug,
  dayFormatter,
  t,
}: {
  episode: Episode;
  slug: string;
  dayFormatter: Intl.DateTimeFormat;
  t: Translator;
}) {
  const sources = episode.sources ?? [];

  return (
    <li className="episode-card">
      <div className="episode-heading">
        <span className="episode-number">{t("episode.number", { number: episode.number })}</span>
        <strong>{episode.name || t("episode.untitled")}</strong>
        {episode.air_date && (
          <time dateTime={episode.air_at ?? episode.air_date} title={episode.air_date}>
            {dayFormatter.format(isoDay(episode.air_date))}
          </time>
        )}
      </div>
      {episode.synopsis && <p className="muted">{episode.synopsis}</p>}
      {sources.some((source) => source.playback_available) && (
        <Link className="secondary" href={`/titles/${slug}?episode=${episode.number}`}>{t("watch.title")}</Link>
      )}
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
        <CharacterAvatar imageUrl={character.image_url} sizes="96px" />
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
  searchParams: Promise<{ episodes_page?: string; characters_page?: string; tab?: string; episode?: string; voice?: string }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  const watchRequested = query.episode !== undefined;
  const navigationRequest = watchRequested ? getWatchNavigation(slug).catch(() => null) : Promise.resolve(null);
  const rawPage = Number(query.episodes_page);
  const requestedPage = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const rawCharactersPage = Number(query.characters_page);
  const charactersPage = Number.isInteger(rawCharactersPage) && rawCharactersPage > 0 ? rawCharactersPage : 1;
  // An existing `?episodes_page=` link must still land on the episode list, so
  // pagination implies the episodes tab when no explicit tab is requested.
  const tab: Tab = isTab(query.tab) ? query.tab : query.episodes_page ? "episodes" : "overview";

  let item;
  let episodesPage = requestedPage;
  try {
    item = await getCatalogItemEpisodes(slug, requestedPage, 20, tab === "characters" ? charactersPage : undefined);
  } catch (error) {
    if (apiErrorStatus(error) !== 404) return <ApiUnavailableState />;
    // The API answers 404 both for a missing title and for an episode page past
    // the end. Retry the first page so an existing title still renders instead
    // of claiming the title does not exist.
    if (requestedPage === 1) notFound();
    try {
      item = await getCatalogItemEpisodes(slug, 1, 20, tab === "characters" ? 1 : undefined);
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
  const castCount = item.characters_count ?? cast.length;
  const castPageCount = Math.max(1, Math.ceil(castCount / 60));
  const credits = item.credits ?? [];
  const mainCredits = credits.filter((credit) => credit.role === "director" || credit.role === "writer" || credit.role === "producer").slice(0, 6);
  const relatedTitles = item.related_titles ?? [];
  // Main characters for the overview: heroes and antagonists only.
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
  let watchSpace: React.ReactNode = null;
  if (watchRequested && episodesCount > 0 && firstEpisode !== null) {
    const loadedNavigation = await navigationRequest;
    const navigation: WatchNavigation = loadedNavigation ?? {
      episode_numbers: Array.from({ length: episodesCount }, (_, index) => index + 1),
      source_groups: [],
    };
    const episodeNumbers = navigation.episode_numbers.length
      ? navigation.episode_numbers
      : Array.from({ length: episodesCount }, (_, index) => index + 1);
    const rawRequested = Number(query.episode);
    const fallbackNumber = Number(episodeNumbers[0] ?? firstEpisode);
    let watchNumber = Number.isInteger(rawRequested) && episodeNumbers.includes(rawRequested)
      ? rawRequested
      : fallbackNumber;
    let watchEpisode;
    try {
      watchEpisode = await getEpisode(slug, watchNumber);
    } catch (error) {
      if (apiErrorStatus(error) !== 404) watchEpisode = null;
      else {
        watchNumber = fallbackNumber;
        try { watchEpisode = await getEpisode(slug, watchNumber); }
        catch { watchEpisode = null; }
      }
    }
    if (watchEpisode) {
      watchSpace = (
        <WatchSpace
          embedded
          slug={slug}
          titleName={item.name}
          episodesCount={episodesCount}
          episodeNumbers={episodeNumbers}
          sourceGroups={navigation.source_groups}
          requestedSourceKey={query.voice}
          currentNumber={watchNumber}
          episode={{
            number: watchEpisode.number,
            name: watchEpisode.name,
            synopsis: watchEpisode.synopsis,
            air_date: watchEpisode.air_date,
            sources: watchEpisode.sources ?? [],
          }}
        />
      );
    }
  }
  const rating = titleRating(item);
  const { t, locale } = await getI18n();
  const dayFormatter = new Intl.DateTimeFormat(intlLocale[locale], {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

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
      <BreadcrumbsJsonLd
        items={[
          { name: t("account.home"), href: "/" },
          { name: t("catalog.title"), href: "/catalog" },
          { name: item.name, href: `/titles/${item.slug}` },
        ]}
      />
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
          <div className={styles.titleNames}>
            {(Object.entries(item.localized_names ?? { ru: item.name, ja: item.original_name ?? "" }) as Array<[string, string]>).filter(([, name]) => name).map(([language, name], index) => (
              <div className={index === 0 ? styles.titleNamePrimary : styles.titleNameSecondary} key={language}>
                <span>{language.toUpperCase()}</span>
                {index === 0 ? <h1 className={styles.heroTitle}>{name}</h1> : <p className={styles.heroOriginal}>{name}</p>}
              </div>
            ))}
          </div>
          <div className={styles.heroMeta}>
            {rating && (
              <Link
                className={styles.metaRating}
                href={`/titles/${item.slug}?tab=community`}
                // Numeric-only tooltip keeps every locale free of plural forms.
                title={`${rating.average} / 10 · ${rating.count}`}
              >
                <span aria-hidden="true">★</span> {rating.average} · {rating.count}
              </Link>
            )}
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
          <ShareButton path={`/titles/${item.slug}`} title={item.name} />
        </div>
        <TitleActions slug={item.slug} firstEpisode={firstEpisode} />
      </article>

      {watchSpace}

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
            {value === "characters" && castCount + credits.length > 0 && <span className={styles.tabCount}>{castCount + credits.length}</span>}
          </Link>
        ))}
      </nav>

      {tab === "overview" && (
        <div className={styles.panel}>
          <section className={styles.block}>
            <h2>{t("title.description")}</h2>
            <p className="muted">{item.synopsis || t("title.descriptionMissing")}</p>
          </section>
          {mainCredits.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("title.authorsMain")}</h2>
                {credits.length > mainCredits.length && <Link href={`/titles/${item.slug}?tab=characters`}>{t("title.peopleAll")}</Link>}
              </div>
              <div className={styles.creditGrid}>
                {mainCredits.map((credit) => (
                  <div className={styles.creditCard} key={`${credit.role}-${credit.creator.slug}`}>
                    <span className={styles.creditInitial} aria-hidden="true">{credit.creator.name.slice(0, 1)}</span>
                    <span><strong>{credit.creator.name}</strong><small>{t(`credit.${credit.role}`)}</small></span>
                  </div>
                ))}
              </div>
            </section>
          )}
          <section className={styles.block}>
            <h2>{t("title.details")}</h2>
            {/* Only facts the hero chips do not already show: runtime, franchise
                and the original spelling. Status/episodes/genres live above. */}
            <dl className={styles.detailsList}>
              <div><dt>{t("catalog.format")}</dt><dd>{t(`type.${item.title_type ?? "anime"}`)}</dd></div>
              {item.duration_minutes ? (
                <div><dt>{t("title.duration")}</dt><dd>{t("title.durationValue", { minutes: item.duration_minutes })}</dd></div>
              ) : null}
              {item.franchise && (
                <div>
                  <dt>{t("title.franchiseLabel")}</dt>
                  <dd><Link href={`/franchises/${item.franchise.slug}`}>{item.franchise.name}</Link></dd>
                </div>
              )}
              {item.original_name && (
                <div><dt>{t("title.originalName")}</dt><dd>{item.original_name}</dd></div>
              )}
            </dl>
          </section>
          {mainCast.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("title.charactersMain")}</h2>
                {cast.length > mainCast.length && (
                  <Link href={`/titles/${item.slug}?tab=characters`}>{t("title.peopleAll")}</Link>
                )}
              </div>
              <div className={styles.castGrid}>
                {mainCast.map((entry) => <CastCard entry={entry} key={entry.character.slug} t={t} />)}
              </div>
            </section>
          )}
          {relatedTitles.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <div>
                  <h2>{t("title.relatedWorks")}</h2>
                  {item.franchise && <p className="muted">{item.franchise.name}</p>}
                </div>
              </div>
              <div className="catalog-shelf">
                {relatedTitles.map((related) => <CatalogCard key={related.slug} item={related} />)}
              </div>
            </section>
          )}
          <NotificationSubscription slug={item.slug} />
          <TitleCollectionControl titleSlug={item.slug} />
          {similar.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("similar.title")}</h2>
                <Link href="/catalog">{t("home.allCatalog")}</Link>
              </div>
              <div className="catalog-shelf">{similar.map((entry) => <CatalogCard key={entry.slug} item={entry} />)}</div>
            </section>
          )}
        </div>
      )}

      {tab === "episodes" && (
        <div className={styles.panel}>
          {episodes.length ? (
            <ol className="episode-list">
              {episodes.map((episode) => <EpisodeCard episode={episode} slug={item.slug} dayFormatter={dayFormatter} t={t} key={episode.number} />)}
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
          <section className={styles.block}>
            <h2>{t("title.characters")}</h2>
            {cast.length ? (
              <div className={styles.castGrid}>
                {cast.map((entry) => <CastCard entry={entry} key={entry.character.slug} t={t} />)}
              </div>
            ) : <p className="muted">{t("title.noCast")}</p>}
            {castPageCount > 1 && (
              <nav className="episode-pagination" aria-label={t("title.characters")}>
                {charactersPage > 1 ? <Link className="secondary" href={`/titles/${item.slug}?tab=characters&characters_page=${charactersPage - 1}`}>{t("common.back")}</Link> : <span />}
                <span>{t("catalog.page", { current: charactersPage, total: castPageCount })} · {castCount}</span>
                {charactersPage < castPageCount ? <Link className="secondary" href={`/titles/${item.slug}?tab=characters&characters_page=${charactersPage + 1}`}>{t("common.next")}</Link> : <span />}
              </nav>
            )}
          </section>
          <section className={styles.block}>
            <h2>{t("title.authors")}</h2>
            {credits.length ? (
              <div className={styles.creditGrid}>
                {credits.map((credit) => (
                  <div className={styles.creditCard} key={`${credit.role}-${credit.creator.slug}`}>
                    <span className={styles.creditInitial} aria-hidden="true">{credit.creator.name.slice(0, 1)}</span>
                    <span><strong>{credit.creator.name}</strong><small>{t(`credit.${credit.role}`)}</small></span>
                  </div>
                ))}
              </div>
            ) : <p className="muted">{t("title.noAuthors")}</p>}
          </section>
        </div>
      )}

      {tab === "community" && <div className={styles.panel}><CommunityPanel slug={item.slug} /></div>}

      {tab === "notes" && <div className={styles.panel}><TitleNoteControl slug={item.slug} /></div>}
    </PageShell>
  );
}
