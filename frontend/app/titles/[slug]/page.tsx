import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArrowRight, ArrowUpRight, User } from "@phosphor-icons/react/dist/ssr";
import { PageShell } from "../../../components/page-shell";
import { CharacterAvatar } from "../../../components/character-avatar";
import { TitleActions } from "../../../components/title-actions";
import { TitleNoteControl } from "../../../components/title-note-control";
import { NotificationSubscription } from "../../../components/notification-subscription";
import { ApiUnavailableState } from "../../../components/api-unavailable";
import { BreadcrumbsJsonLd } from "../../../components/breadcrumbs-jsonld";
import { CommunityPanel } from "../../../components/community-panel";
import { TitleCollectionControl } from "../../../components/title-collection-control";
import { CatalogCard } from "../../../components/catalog-card";
import { WatchSpace } from "../../../components/watch-space";
import {
  apiErrorStatus,
  getCatalogItemEpisodes,
  getCatalogItemMetadata,
  getEpisode,
  getFirstEpisodeNumber,
  getSimilarTitles,
  getWatchNavigation,
  type CatalogItem,
  type Episode,
  type TitleCastEntry,
  type TitleCreditEntry,
  type WatchNavigation,
} from "../../../lib/api";
import { absoluteUrl, metaDescription } from "../../../lib/site";
import { hasCharacterArt } from "../../../lib/character-image";
import { titleRating } from "../../../lib/rating";
import { NO_INDEX_ROBOTS, titleOpenGraphType, titleSchemaType, titleWatchHref } from "../../../lib/seo";
import { resolveTitleEpisodeRequest, titleTemplateState } from "../../../lib/title-template";
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
    // Metadata needs title fields only. Requesting one episode avoids pulling
    // the full episode catalogue (more than a thousand rows for long series).
    item = await getCatalogItemMetadata(slug);
  } catch (error) {
    // Degraded API still needs sane metadata; the page itself shows the
    // unavailable state. The page component owns the 404: notFound() inside
    // generateMetadata races the render and can answer 200.
    if (apiErrorStatus(error) === 404) return { title: t("title.notFound") };
    return {
      title: "AniCast",
      description: t("meta.description"),
      alternates: { canonical: `/titles/${encodeURIComponent(slug)}` },
      robots: NO_INDEX_ROBOTS,
    };
  }

  const description = metaDescription(item.synopsis, t("meta.description"));
  return {
    title: item.name,
    description,
    alternates: { canonical: `/titles/${item.slug}` },
    openGraph: {
      type: titleOpenGraphType(item.title_type),
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
  const template = titleTemplateState(item.title_type, item.episodes_count);
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
  if (template.structuredEpisodeCount) data.numberOfEpisodes = template.structuredEpisodeCount;
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
  const episodeLabel = t("episode.number", { number: episode.number });
  const episodeName = episode.name || t("episode.untitled");

  return (
    <li>
      <Link
        className={styles.episodeCard}
        href={titleWatchHref(slug, episode.number)}
        aria-label={`${episodeLabel}: ${episodeName}`}
      >
        <span className={styles.episodeBody}>
          <span className={styles.episodeHeading}>
            <span className={styles.episodeNumber}>{episodeLabel}</span>
            <strong>{episodeName}</strong>
          </span>
          {episode.synopsis && <span className={styles.episodeSynopsis}>{episode.synopsis}</span>}
        </span>
        <span className={styles.episodeMeta}>
          {episode.air_date && (
            <time dateTime={episode.air_at ?? episode.air_date} title={episode.air_date}>
              {dayFormatter.format(isoDay(episode.air_date))}
            </time>
          )}
          <span className={styles.episodeArrow} aria-hidden="true">
            <ArrowRight size={18} weight="bold" />
          </span>
        </span>
      </Link>
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

function CreditCard({ credit }: { credit: TitleCreditEntry }) {
  return (
    <Link className={styles.creditCard} href={`/creators/${credit.creator.slug}`}>
      <span className={styles.creditAvatar} aria-hidden="true">
        {hasCharacterArt(credit.creator.image_url) ? (
          <Image src={credit.creator.image_url} alt="" fill sizes="44px" quality={92} referrerPolicy="no-referrer" />
        ) : <User size={22} weight="bold" />}
      </span>
      <span className={styles.creditBody}><strong>{credit.creator.name}</strong><small>{credit.role_label}</small></span>
      <ArrowUpRight className={styles.creditArrow} aria-hidden="true" size={17} />
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
  const rawPage = Number(query.episodes_page);
  const requestedPage = Number.isInteger(rawPage) && rawPage > 0 ? rawPage : 1;
  const rawCharactersPage = Number(query.characters_page);
  const charactersPage = Number.isInteger(rawCharactersPage) && rawCharactersPage > 0 ? rawCharactersPage : 1;
  // An existing `?episodes_page=` link must still land on the episode list, so
  // pagination implies the episodes tab when no explicit tab is requested.
  const requestedTab: Tab = isTab(query.tab) ? query.tab : query.episodes_page ? "episodes" : "overview";
  const characterPayloadPage = requestedTab === "characters" ? charactersPage : 1;
  // A movie episode tab is normalized to Overview after the title type is
  // known, so keep enough overview cast in that response.
  const characterPayloadSize = requestedTab === "characters"
    ? 60
    : requestedTab === "overview" || requestedTab === "episodes" ? 8 : 1;

  let item;
  try {
    item = await getCatalogItemEpisodes(
      slug, requestedPage, 20, characterPayloadPage, characterPayloadSize,
    );
  } catch (error) {
    if (apiErrorStatus(error) !== 404) return <ApiUnavailableState />;
    // The API answers 404 both for a missing title and for an episode page past
    // the end. Probe the first page only to distinguish those cases.
    if (requestedPage === 1) notFound();
    try {
      await getCatalogItemEpisodes(slug, 1, 1, 1, 1);
    } catch (retryError) {
      if (apiErrorStatus(retryError) === 404) notFound();
      return <ApiUnavailableState />;
    }
    // The title exists but the requested episode-list page does not. Serving
    // page one here would create a soft duplicate at an arbitrary URL.
    notFound();
  }

  const episodes = item.episodes ?? [];
  const episodesCount = item.episodes_count ?? episodes.length;
  const template = titleTemplateState(item.title_type, episodesCount);
  const tab: Tab = requestedTab === "episodes" && !template.showEpisodeTab
    ? "overview"
    : requestedTab;
  const pageCount = Math.max(1, Math.ceil(episodesCount / 20));
  const genres = item.genres ?? [];
  const cast = item.characters ?? [];
  const castCount = item.characters_count ?? cast.length;
  const castPageCount = Math.max(1, Math.ceil(castCount / 60));
  const credits = item.credits ?? [];
  // The API orders exact per-work credits by creative importance. The overview
  // intentionally stays editorial: three people, while the full list remains
  // available on the people tab.
  const mainCredits = credits.slice(0, 3);
  const relatedTitles = item.related_titles ?? [];
  // Main characters for the overview: heroes and antagonists only.
  const mainCast = cast
    .filter((entry) => entry.role === "protagonist" || entry.role === "antagonist")
    .slice(0, 8);
  const [similar, firstEpisode, loadedNavigation] = await Promise.all([
    tab === "overview" ? getSimilarTitles(slug) : Promise.resolve([]),
    // The hero action must point at the real first episode regardless of which
    // episode page the viewer is on, so it is resolved independently.
    requestedPage === 1 && episodes.length
      ? Promise.resolve(Math.min(...episodes.map((episode) => episode.number)))
      : getFirstEpisodeNumber(slug),
    episodesCount > 0 ? getWatchNavigation(slug).catch(() => null) : Promise.resolve(null),
  ]);
  let watchSpace: React.ReactNode = null;
  let watchLoadFailed = false;
  const navigationPlayableNumbers = loadedNavigation?.playable_episode_numbers
    ?? loadedNavigation?.episode_numbers
    ?? [];
  let watchActionHref = tab !== "overview" && navigationPlayableNumbers.length
    ? titleWatchHref(item.slug, navigationPlayableNumbers[0])
    : undefined;
  let watchRetryNumber = firstEpisode;
  if (tab === "overview" && episodesCount > 0 && firstEpisode !== null) {
    const navigation: WatchNavigation = loadedNavigation ?? {
      episode_numbers: [],
      source_groups: [],
    };
    // The current detail page is a safe degraded fallback, but it is not a
    // complete catalogue for long titles and therefore cannot validate gaps.
    const catalogNumbersKnown = loadedNavigation?.catalog_episode_numbers !== undefined;
    const catalogEpisodeNumbers = loadedNavigation?.catalog_episode_numbers
      ?? episodes.map((episode) => episode.number);
    const playableEpisodeNumbers = navigation.playable_episode_numbers
      ?? navigation.episode_numbers;
    const fallbackNumber = Number(playableEpisodeNumbers[0] ?? firstEpisode);
    const resolvedRequest = resolveTitleEpisodeRequest(
      template.playbackPresentation,
      fallbackNumber,
      query.episode,
      catalogNumbersKnown ? catalogEpisodeNumbers : undefined,
    );
    let watchNumber = resolvedRequest.number;
    let invalidEpisodeRequest = resolvedRequest.corrected;
    watchRetryNumber = watchNumber;

    try {
      let watchEpisode;
      try {
        watchEpisode = await getEpisode(slug, watchNumber);
      } catch (error) {
        if (apiErrorStatus(error) !== 404 || watchNumber === fallbackNumber) throw error;
        watchNumber = fallbackNumber;
        watchRetryNumber = fallbackNumber;
        invalidEpisodeRequest = true;
        watchEpisode = await getEpisode(slug, fallbackNumber);
      }
      const hasCurrentPlayback = (watchEpisode.sources ?? []).some((source) => source.playback_available);
      const playableWithoutCurrent = playableEpisodeNumbers.filter((number) => number !== watchNumber);
      const resolvedPlayableNumbers = hasCurrentPlayback
        ? [...playableWithoutCurrent, watchNumber].sort((left, right) => left - right)
        : playableWithoutCurrent;
      // Metadata-only episodes remain part of the catalogue but never become
      // available player destinations.
      // Presentation belongs to the title template, not to today's provider
      // coverage. An airing series with one playable episode must not turn
      // into a movie and then change its layout after the next release.
      const playbackPresentation = template.playbackPresentation;
      watchSpace = (
        <WatchSpace
          slug={slug}
          titleName={item.name}
          playableEpisodeNumbers={resolvedPlayableNumbers}
          sourceGroups={navigation.source_groups}
          requestedSourceKey={query.voice}
          currentNumber={watchNumber}
          playbackPresentation={playbackPresentation}
          navigationDegraded={!loadedNavigation}
          invalidEpisodeRequest={invalidEpisodeRequest}
          episode={{
            synopsis: watchEpisode.synopsis,
            sources: watchEpisode.sources ?? [],
          }}
        />
      );
      watchActionHref = hasCurrentPlayback
        ? "#watch"
        : resolvedPlayableNumbers.length
          ? titleWatchHref(item.slug, resolvedPlayableNumbers[0])
          : undefined;
    } catch {
      watchLoadFailed = true;
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
              quality={92}
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
                {index === 0 ? <h1 className={styles.heroTitle} lang={language}>{name}</h1> : <p className={styles.heroOriginal} lang={language}>{name}</p>}
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
            {template.showEpisodeCount && <span>{t("title.episodesCount", { count: episodesCount })}</span>}
            {item.duration_minutes ? <span>{t("title.durationValue", { minutes: item.duration_minutes })}</span> : null}
          </div>
          {genres.length > 0 && (
            <div className={styles.heroGenres}>
              {genres.map((genre) => (
                <Link href={`/catalog?genre=${encodeURIComponent(genre.slug)}`} key={genre.slug}>{genre.name}</Link>
              ))}
            </div>
          )}
        </div>
        <TitleActions
          slug={item.slug}
          watchHref={watchActionHref}
        />
      </article>

      <nav className={styles.tabs} aria-label={t("title.tabOverview")}>
        {TABS.filter((value) => value !== "episodes" || template.showEpisodeTab).map((value) => (
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
          {(watchSpace || watchLoadFailed || episodesCount === 0) && (
            <section className={styles.watchSection} id="watch">
              <h2>{t("watch.title")}</h2>
              {watchSpace ?? (
                <div className={styles.watchAvailability} role={watchLoadFailed ? "alert" : "status"}>
                  <strong>{watchLoadFailed
                    ? t("watch.loadFailed")
                    : t("watch.noEpisodesTitle")}</strong>
                  <span>{watchLoadFailed
                    ? t("watch.loadFailedText")
                    : item.status === "planned" ? t("watch.noEpisodesPlanned") : t("watch.noEpisodesText")}</span>
                  {watchLoadFailed && watchRetryNumber !== null && (
                    <Link className="secondary inline-button" href={titleWatchHref(item.slug, watchRetryNumber)}>
                      {t("common.retry")}
                    </Link>
                  )}
                </div>
              )}
            </section>
          )}
          {item.synopsis && (
            <section className={`${styles.block} ${styles.descriptionCard}`}>
              <h2>{t("title.description")}</h2>
              <p>{item.synopsis}</p>
            </section>
          )}
          {mainCredits.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("title.authorsMain")}</h2>
                {credits.length > mainCredits.length && <Link href={`/titles/${item.slug}?tab=characters`}>{t("title.peopleAll")}</Link>}
              </div>
              <div className={styles.creditGrid}>
                {mainCredits.map((credit) => <CreditCard credit={credit} key={`${credit.role}-${credit.creator.slug}`} />)}
              </div>
            </section>
          )}
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
              <div className={styles.relatedRail}>
                {relatedTitles.map((related) => <CatalogCard key={related.slug} item={related} variant="media" />)}
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
              <div className={styles.relatedRail}>{similar.map((entry) => <CatalogCard key={entry.slug} item={entry} variant="media" />)}</div>
            </section>
          )}
        </div>
      )}

      {tab === "episodes" && (
        <div className={styles.panel}>
          {episodes.length ? (
            <ol className={styles.episodeList}>
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
              {requestedPage > 1 && (
                <Link className="secondary" href={`/titles/${item.slug}?tab=episodes&episodes_page=${requestedPage - 1}`}>
                  {t("common.back")}
                </Link>
              )}
              <span>{t("catalog.page", { current: requestedPage, total: pageCount })}</span>
              {requestedPage < pageCount && (
                <Link className="secondary" href={`/titles/${item.slug}?tab=episodes&episodes_page=${requestedPage + 1}`}>
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
                {credits.map((credit) => <CreditCard credit={credit} key={`${credit.role}-${credit.creator.slug}`} />)}
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
