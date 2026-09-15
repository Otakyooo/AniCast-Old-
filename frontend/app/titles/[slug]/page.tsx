import { headers } from "next/headers";
import Link from "next/link";
import Image from "next/image";
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ArrowRight, User } from "@phosphor-icons/react/dist/ssr";
import { PageShell } from "../../../components/page-shell";
import { CharacterAvatar } from "../../../components/character-avatar";
import { RailScroller } from "../../../components/rail-scroller";
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
  type Special,
  type TitleCastEntry,
  type TitleCreditEntry,
  type WatchNavigation,
} from "../../../lib/api";
import { absoluteUrl, metaDescription } from "../../../lib/site";
import { hasCharacterArt } from "../../../lib/character-image";
import { episodeCountLabel } from "../../../lib/episode-count";
import { dedupeByFranchise } from "../../../lib/similar-shelf";
import { titleNameRows } from "../../../lib/title-names";
import { titleRating } from "../../../lib/rating";
import { NO_INDEX_ROBOTS, jsonLdScript, titleOpenGraphType, titleSchemaType, titleWatchHref } from "../../../lib/seo";
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
      // A plain "AniCast" would come back as "AniCast — AniCast" through the
      // root template, so the fallback title is set absolutely.
      title: { absolute: "AniCast" },
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
async function TitleJsonLd({ item }: { item: CatalogItem }) {
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
  // Structured data must match what the page shows. The badge needs
  // MIN_RATING_VOTES before an average reads as anything but noise, so the same
  // gate decides the markup — otherwise a single vote would publish a rating
  // that appears nowhere on the page.
  const rating = titleRating(item);
  if (rating) {
    data.aggregateRating = {
      "@type": "AggregateRating",
      ratingValue: rating.average,
      ratingCount: rating.count,
      bestRating: 10,
      worstRating: 1,
    };
  }
  return <script nonce={(await headers()).get("x-nonce") ?? undefined} type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(data) }} />;
}

function isTab(value: string | undefined): value is Tab {
  return TABS.includes((value ?? "") as Tab);
}

/** "12 430 оценок" with the locale's plural form; numeric-only stays
 * locale-formatted so en/ru share one helper. */
function ratingCountLabel(count: number, locale: string, t: Translator) {
  const formatted = new Intl.NumberFormat(intlLocale[locale as keyof typeof intlLocale]).format(count);
  if (locale === "ru") {
    const mod10 = count % 10;
    const mod100 = count % 100;
    if (mod10 === 1 && mod100 !== 11) return t("title.ratingCountOne", { count: formatted });
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return t("title.ratingCountFew", { count: formatted });
    return t("title.ratingCountMany", { count: formatted });
  }
  return count === 1
    ? t("title.ratingCountOne", { count: formatted })
    : t("title.ratingCountMany", { count: formatted });
}

/** Noon-UTC anchor so a plain YYYY-MM-DD renders the same day in every timezone. */
function isoDay(value: string): Date {
  return new Date(`${value}T12:00:00Z`);
}

function SpecialCard({
  special,
  slug,
  voice,
  dayFormatter,
  t,
}: {
  special: Special;
  slug: string;
  voice?: string;
  dayFormatter: Intl.DateTimeFormat;
  t: Translator;
}) {
  const label = t("episode.special", { number: special.number });
  const name = special.name || t("episode.untitled");

  return (
    <li>
      <Link
        className={styles.episodeCard}
        href={titleWatchHref(slug, special.number, voice, 0)}
        prefetch={false}
        aria-label={`${label}: ${name}`}
      >
        <span className={styles.episodeBody}>
          <span className={styles.episodeHeading}>
            <span className={styles.episodeNumber}>{label}</span>
            <strong>{name}</strong>
          </span>
          {special.synopsis && <span className={styles.episodeSynopsis}>{special.synopsis}</span>}
        </span>
        <span className={styles.episodeMeta}>
          {special.air_date && (
            <time dateTime={special.air_date} title={special.air_date}>
              {dayFormatter.format(isoDay(special.air_date))}
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

function EpisodeCard({
  episode,
  slug,
  voice,
  dayFormatter,
  t,
}: {
  episode: Episode;
  slug: string;
  voice?: string;
  dayFormatter: Intl.DateTimeFormat;
  t: Translator;
}) {
  const episodeLabel = t("episode.number", { number: episode.number });
  const episodeName = episode.name || t("episode.untitled");

  return (
    <li>
      <Link
        className={styles.episodeCard}
        href={titleWatchHref(slug, episode.number, voice)}
        prefetch={false}
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
  // Imported feeds join every creative role into one label ("Режиссёр ·
  // Режиссёр эпизодов · Раскадровка"), which outgrows the name. The card
  // shows the primary role and keeps the full list in the tooltip.
  const primaryRole = credit.role_label.split("·")[0]?.trim() || credit.role_label;
  return (
    <Link
      className={styles.creditCard}
      href={`/creators/${credit.creator.slug}`}
      title={primaryRole !== credit.role_label ? credit.role_label : undefined}
    >
      <span className={styles.creditAvatar} aria-hidden="true">
        {hasCharacterArt(credit.creator.image_url) ? (
          <Image src={credit.creator.image_url} alt="" fill sizes="44px" quality={92} referrerPolicy="no-referrer" />
        ) : <User size={22} weight="bold" />}
      </span>
      <span className={styles.creditBody}><strong>{credit.creator.name}</strong><small>{primaryRole}</small></span>
    </Link>
  );
}

/** One numbered step of the franchise watch order. The counter answers "what
 * do I watch next", which a plain poster grid never did. */
function WatchOrderCard({
  related,
  step,
  current,
  t,
}: {
  related: NonNullable<CatalogItem["related_titles"]>[number];
  step: number;
  current: boolean;
  t: Translator;
}) {
  return (
    <Link
      className={current ? `${styles.watchOrderCard} ${styles.watchOrderCurrent}` : styles.watchOrderCard}
      href={`/titles/${related.slug}`}
      title={related.name}
    >
      <span className={styles.watchOrderPoster}>
        {related.poster_url ? (
          <Image
            src={related.poster_url}
            alt=""
            fill
            sizes="(max-width: 767px) 40vw, 168px"
            quality={92}
            referrerPolicy="no-referrer"
          />
        ) : null}
        <span className={styles.watchOrderStep} aria-hidden="true">{step}</span>
      </span>
      <span className={styles.watchOrderBody}>
        <strong>{related.name}</strong>
        <small>{[related.year, related.title_type ? t(`type.${related.title_type}`) : ""].filter(Boolean).join(" · ")}</small>
      </span>
    </Link>
  );
}

export default async function CatalogDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ episodes_page?: string; characters_page?: string; tab?: string; episode?: string; voice?: string; season?: string }>;
}) {
  const { slug } = await params;
  const query = await searchParams;
  // A special can share the number with a regular episode, so the link says which
  // run it means. Absent means the work's own episodes.
  const season = query.season === "0" ? 0 : 1;
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
  const specials = item.specials ?? [];
  // MAL gives a separately-released special its own entry while keeping one that
  // aired inside the run with the series, and the backend reports which is which.
  const specialsWithRun = specials.filter((special) => special.released_with_run);
  const specialsSeparate = specials.filter((special) => !special.released_with_run);
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
  // Main characters for the overview: heroes and antagonists only, capped at
  // the desktop cast grid width (6 columns) so the row never strands orphans.
  const mainCast = cast
    .filter((entry) => entry.role === "protagonist" || entry.role === "antagonist")
    .slice(0, 6);
  const [similarRaw, firstEpisode, loadedNavigation] = await Promise.all([
    tab === "overview" ? getSimilarTitles(slug) : Promise.resolve([]),
    // The hero action must point at the real first episode regardless of which
    // episode page the viewer is on, so it is resolved independently.
    requestedPage === 1 && episodes.length
      ? Promise.resolve(Math.min(...episodes.map((episode) => episode.number)))
      : getFirstEpisodeNumber(slug),
    episodesCount > 0 ? getWatchNavigation(slug).catch(() => null) : Promise.resolve(null),
  ]);
  // Sibling seasons of one franchise must not crowd out other similar titles.
  const similarUnique = dedupeByFranchise(similarRaw);
  let watchProps: React.ComponentProps<typeof WatchSpace> | null = null;
  let watchLoadFailed = false;
  const navigationPlayableNumbers = loadedNavigation?.playable_episode_numbers
    ?? loadedNavigation?.episode_numbers
    ?? [];
  let watchActionHref = tab !== "overview" && navigationPlayableNumbers.length
    ? titleWatchHref(item.slug, navigationPlayableNumbers.includes(Number(query.episode)) ? Number(query.episode) : navigationPlayableNumbers[0], query.voice)
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
        watchEpisode = await getEpisode(slug, watchNumber, season);
      } catch (error) {
        if (apiErrorStatus(error) !== 404 || watchNumber === fallbackNumber) throw error;
        watchNumber = fallbackNumber;
        watchRetryNumber = fallbackNumber;
        invalidEpisodeRequest = true;
        watchEpisode = await getEpisode(slug, fallbackNumber, season);
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
      watchProps = {
          slug,
          titleName: item.name,
          totalEpisodeCount: episodesCount,
          playableEpisodeNumbers: resolvedPlayableNumbers,
          sourceGroups: navigation.source_groups,
          requestedSourceKey: query.voice,
          currentNumber: watchNumber,
          playbackPresentation,
          navigationDegraded: !loadedNavigation,
          invalidEpisodeRequest,
          episode: {
            synopsis: watchEpisode.synopsis,
            sources: watchEpisode.sources ?? [],
          },
      };
      watchActionHref = hasCurrentPlayback
        ? "#watch"
        : resolvedPlayableNumbers.length
          ? titleWatchHref(item.slug, resolvedPlayableNumbers[0])
          : undefined;
    } catch {
      watchLoadFailed = true;
    }
  }
  // The catch above handles loading only; rendering errors use the route boundary.
  const watchSpace = watchProps ? <WatchSpace {...watchProps} /> : null;
  const rating = titleRating(item);
  const { t, locale } = await getI18n();
  const dayFormatter = new Intl.DateTimeFormat(intlLocale[locale], {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  // Raw counts like "1180" read as noise in a tab; "1,2 тыс." keeps the scale.
  const compactCount = new Intl.NumberFormat(intlLocale[locale], { notation: "compact" }).format;

  const tabHref = (value: Tab, page = 1) => {
    const state = new URLSearchParams();
    if (value !== "overview") state.set("tab", value);
    const episodeNumber = Number(query.episode);
    if (Number.isInteger(episodeNumber) && episodeNumber > 0) state.set("episode", String(episodeNumber));
    if (query.voice?.trim()) state.set("voice", query.voice.trim());
    if (page > 1 && value === "episodes") state.set("episodes_page", String(page));
    if (page > 1 && value === "characters") state.set("characters_page", String(page));
    return `/titles/${item.slug}${state.size ? `?${state}` : ""}#${value === "overview" ? "watch" : "title-tabs"}`;
  };
  const tabLabel: Record<Tab, string> = {
    overview: t("title.tabOverview"),
    episodes: t("title.tabEpisodes"),
    characters: t("title.tabCharacters"),
    community: t("title.tabCommunity"),
    notes: t("title.tabNotes"),
  };
  // Watch focus: an explicit episode request means the viewer came to watch,
  // not to read. The hero compacts and the people blocks step aside until the
  // viewer returns to the plain title page.
  const watchFocus = Boolean(query.episode) && tab === "overview";
  const secondaryTabs = TABS.filter((value) => ["characters", "community", "notes"].includes(value));
  const primaryTabs = TABS.filter((value) => !["characters", "community", "notes"].includes(value));

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
      <article className={watchFocus ? `${styles.hero} ${styles.heroCompact}` : styles.hero}>
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
          {item.franchise && (
            // The franchise link replaces the useless "Аниме" eyebrow: it is
            // the one label here that actually navigates somewhere.
            <Link className={`eyebrow ${styles.heroFranchise}`} href={`/franchises/${item.franchise.slug}`}>
              {t("title.franchiseLabel")}: {item.franchise.name}
            </Link>
          )}
          {(() => {
            // One primary headline; every other spelling collapses into an
            // "Other names" disclosure instead of a wall of RU/EN/JA rows.
            const rows = titleNameRows(item.localized_names, item.name, item.original_name);
            const [primary, ...others] = rows;
            return (
              <>
                <h1 className={styles.heroTitle} lang={primary.language}>{primary.name}</h1>
                {others.length > 0 && (
                  <details className={styles.otherNames}>
                    <summary>{t("title.otherNames")} ({others.length})</summary>
                    {others.map((row) => (
                      <p className={styles.heroOriginal} lang={row.language} key={`${row.language}-${row.name}`}>
                        {row.showLanguageTag && <span aria-hidden="true">{row.language.toUpperCase()}</span>}
                        {row.name}
                      </p>
                    ))}
                  </details>
                )}
              </>
            );
          })()}
          <div className={styles.heroMeta}>
            {rating && (
              <Link
                className={styles.metaRating}
                href={tabHref("community")}
                title={`${rating.average} / 10`}
              >
                <span aria-hidden="true">★</span> {rating.average} · {ratingCountLabel(rating.count, locale, t)}
              </Link>
            )}
            <span>
              {item.status === "ongoing" && item.year
                ? t("title.yearsOngoing", { year: item.year })
                : item.year ?? t("title.yearUnknown")}
            </span>
            <span className={item.status === "ongoing" ? styles.metaOngoing : undefined}>
              {item.status ? t(`status.${item.status}`) : t("status.unknown")}
            </span>
            {template.showEpisodeCount && (
              <span>
                {episodeCountLabel(t, locale, episodesCount)}
                {item.duration_minutes
                  ? ` × ${t("title.minutesValue", { minutes: item.duration_minutes })}`
                  : ""}
              </span>
            )}
          </div>
          {genres.length > 0 && (
            <div className={styles.heroGenres}>
              {genres.map((genre) => (
                <Link href={`/catalog?genre=${encodeURIComponent(genre.slug)}`} key={genre.slug}>{genre.name}</Link>
              ))}
            </div>
          )}
          {/* A clamped synopsis teaser answers "what is this about" in the
              first screen; "Подробнее" anchors to the full description. */}
          {item.synopsis && (
            <p className={styles.heroSynopsis}>
              {item.synopsis}
              {" "}
              <a className={styles.heroSynopsisMore} href="#title-description">{t("title.synopsisMore")}</a>
            </p>
          )}
        </div>
        <TitleActions
          slug={item.slug}
          watchHref={watchActionHref}
          explicitEpisode={Boolean(query.episode)}
        />
        {/* Collection membership is a personal folder action, not a viewing
            state: it stays a quiet cluster under the hero buttons. Finished
            titles get no "notify about new episodes" control at all. */}
        <div className={styles.heroSubscribe}>
          <TitleCollectionControl titleSlug={item.slug} />
          {item.status !== "finished" && <NotificationSubscription slug={item.slug} />}
        </div>
      </article>

      <nav className={styles.tabs} id="title-tabs" aria-label={t("title.tabOverview")}>
        {primaryTabs.filter((value) => value !== "episodes" || template.showEpisodeTab).map((value) => (
          <Link
            className={`${styles.tab} ${value === tab ? styles.tabActive : ""}`}
            href={tabHref(value)}
            prefetch={false}
            aria-current={value === tab ? "page" : undefined}
            key={value}
          >
            {tabLabel[value]}
            {value === "episodes" && episodesCount > 0 && <span className={styles.tabCount}>{compactCount(episodesCount)}</span>}
          </Link>
        ))}
        {/* Watching is the core task; people/community/notes are secondary
            destinations and step back both visually and positionally. */}
        <span className={styles.tabsSecondary}>
          {secondaryTabs.map((value) => (
            <Link
              className={`${styles.tab} ${value === tab ? styles.tabActive : ""}`}
              href={tabHref(value)}
              prefetch={false}
              aria-current={value === tab ? "page" : undefined}
              key={value}
            >
              {tabLabel[value]}
              {value === "characters" && castCount + credits.length > 0 && <span className={styles.tabCount}>{compactCount(castCount + credits.length)}</span>}
            </Link>
          ))}
        </span>
      </nav>

      {tab === "overview" && (
        <div className={styles.panel}>
          {(watchSpace || watchLoadFailed || episodesCount === 0) && (
            <section className={styles.watchSection} id="watch">
              <h2>{t("watch.sectionTitle")}</h2>
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
          {/* The description is the page's core content, so it sits above the
              people blocks. Without a synopsis there is nothing honest to
              render — the missing text is a data gap, not a UI state. */}
          {item.synopsis && (
            <section className={`${styles.block} ${styles.descriptionCard}`} id="title-description">
              <h2>{t("title.description")}</h2>
              <p>{item.synopsis}</p>
            </section>
          )}
          {relatedTitles.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <div>
                  <h2>{t("title.watchOrder")}</h2>
                  <p className="muted">{t("title.watchOrderHint")}</p>
                </div>
                {item.franchise && (
                  <Link href={`/franchises/${item.franchise.slug}`}>{item.franchise.name}</Link>
                )}
              </div>
              {/* Numbered chronology of the franchise: the step counter says
                  what to watch next, which a plain poster grid never did. */}
              <RailScroller railClassName={styles.watchOrderRail}>
                {[
                  ...relatedTitles,
                  { slug: item.slug, name: item.name, poster_url: item.poster_url ?? null, title_type: item.title_type ?? null, status: item.status ?? null, year: item.year ?? null },
                ]
                  .sort((left, right) => (
                    (left.year ?? 99999) - (right.year ?? 99999)
                    || left.name.localeCompare(right.name)
                  ))
                  .map((related, index) => (
                    <WatchOrderCard
                      related={related}
                      step={index + 1}
                      current={related.slug === item.slug}
                      t={t}
                      key={related.slug}
                    />
                  ))}
              </RailScroller>
            </section>
          )}
          {similarUnique.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("similar.title")}</h2>
                {/* Similar titles are not the whole catalog; the honest
                    adjacent destination is the shared genre. */}
                {genres[0] && (
                  <Link href={`/catalog?genre=${encodeURIComponent(genres[0].slug)}`}>
                    {t("similar.moreInGenre", { genre: genres[0].name })}
                  </Link>
                )}
              </div>
              <RailScroller railClassName={styles.relatedRail}>{similarUnique.map((entry) => <CatalogCard key={entry.slug} item={entry} variant="media" />)}</RailScroller>
            </section>
          )}
          {/* People are reference material, not the viewing task: they sit
            below description, watch order and similar titles, and step aside
            entirely while the viewer is watching an episode. */}
          {!watchFocus && mainCredits.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("title.authorsMain")}</h2>
              </div>
              <div className={styles.creditGrid}>
                {mainCredits.map((credit) => <CreditCard credit={credit} key={`${credit.role}-${credit.creator.slug}`} />)}
              </div>
            </section>
          )}
          {!watchFocus && mainCast.length > 0 && (
            <section className={styles.block}>
              <div className="section-heading">
                <h2>{t("title.charactersMain")}</h2>
                {cast.length > mainCast.length && (
                  <Link href={tabHref("characters")}>{t("title.allCharacters")}</Link>
                )}
              </div>
              <div className={styles.castGrid}>
                {mainCast.map((entry) => <CastCard entry={entry} key={entry.character.slug} t={t} />)}
              </div>
            </section>
          )}
        </div>
      )}

      {tab === "episodes" && (
        <div className={styles.panel}>
          {episodes.length ? (
            <ol className={styles.episodeList}>
              {episodes.map((episode) => <EpisodeCard episode={episode} slug={item.slug} voice={query.voice} dayFormatter={dayFormatter} t={t} key={episode.number} />)}
            </ol>
          ) : (
            <div className="empty-state" role="status">
              <strong>{t("title.noEpisodes")}</strong>
              <span>{t("title.noEpisodesText")}</span>
            </div>
          )}
          {specials.length > 0 && (
            <section className={styles.panel}>
              <h3>{t("title.specials")}</h3>
              {specialsWithRun.length > 0 && (
                <>
                  <h4>{t("title.specialsWithRun")}</h4>
                  <ol className={styles.episodeList}>
                    {specialsWithRun.map((special) => (
                      <SpecialCard special={special} slug={item.slug} voice={query.voice} dayFormatter={dayFormatter} t={t} key={special.number} />
                    ))}
                  </ol>
                </>
              )}
              {specialsSeparate.length > 0 && (
                <>
                  <h4>{t("title.specialsSeparate")}</h4>
                  <p>{t("title.specialsSeparateHint")}</p>
                  <ol className={styles.episodeList}>
                    {specialsSeparate.map((special) => (
                      <SpecialCard special={special} slug={item.slug} voice={query.voice} dayFormatter={dayFormatter} t={t} key={special.number} />
                    ))}
                  </ol>
                </>
              )}
            </section>
          )}
          {pageCount > 1 && (
            <nav className="episode-pagination" aria-label={t("title.episodes")}>
              {requestedPage > 1 && (
                <Link className="secondary" href={tabHref("episodes", requestedPage - 1)}>
                  {t("common.back")}
                </Link>
              )}
              <span>{t("catalog.page", { current: requestedPage, total: pageCount })}</span>
              {requestedPage < pageCount && (
                <Link className="secondary" href={tabHref("episodes", requestedPage + 1)}>
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
                {charactersPage > 1 ? <Link className="secondary" href={tabHref("characters", charactersPage - 1)}>{t("common.back")}</Link> : <span />}
                <span>{t("catalog.page", { current: charactersPage, total: castPageCount })} · {castCount}</span>
                {charactersPage < castPageCount ? <Link className="secondary" href={tabHref("characters", charactersPage + 1)}>{t("common.next")}</Link> : <span />}
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

      {/* The tab name alone does not explain what "notes" are; one muted line
          keeps the personal-context purpose clear. */}
      {tab === "notes" && (
        <div className={styles.panel}>
          <p className="muted">{t("notes.subtitle")}</p>
          <TitleNoteControl slug={item.slug} />
        </div>
      )}
    </PageShell>
  );
}
