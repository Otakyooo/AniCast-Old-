import { headers } from "next/headers";
import Link from "next/link";
import type { Metadata } from "next";
import { CatalogCard } from "../components/catalog-card";
import { ContinueWatchingBlock } from "../components/continue-watching-block";
import { NextPartShelf } from "../components/next-part-shelf";
import { RailScroller } from "../components/rail-scroller";
import { RecommendationShelf } from "../components/recommendation-shelf";
import { ScheduleStrip } from "../components/schedule-strip";
import { AiringRail, RecentEpisodesRail } from "../components/home-release-shelves";
import { PageShell } from "../components/page-shell";
import {
  emptyPage,
  getAiringTitles,
  getCatalog,
  getRecentEpisodes,
  getSchedule,
  type CatalogItem,
  type ScheduleItem,
  type ScheduleResponse,
} from "../lib/api";
import { addDays, localDayKey } from "../lib/schedule";
import { dedupeShelf } from "../lib/home-shelves";
import { getI18n } from "../i18n/server";
import { jsonLdScript, websiteJsonLd } from "../lib/seo";
import styles from "./home.module.css";

export const dynamic = "force-dynamic";

const SHELF_SIZE = 12;
/** Below this size a shelf reads as abandoned rather than curated. */
const MIN_FULL_SHELF = 6;
/** A shelf with fewer cards is dropped: a titled one-card strip looks broken. */
const MIN_VISIBLE_SHELF = 4;
/** The home release shelf promises exactly one week of aired episodes. */
const RECENT_EPISODE_DAYS = 7;

export async function generateMetadata(): Promise<Metadata> {
  const { t } = await getI18n();
  return {
    title: { absolute: t("meta.homeTitle") },
    description: t("meta.homeDescription"),
    alternates: { canonical: "/" },
  };
}

function CatalogShelf({
  title,
  subtitle,
  items,
  href,
  linkLabel,
  emptyLabel,
  showLibraryControls = true,
}: {
  title: string;
  subtitle: string;
  items: CatalogItem[];
  href: string;
  linkLabel: string;
  emptyLabel: string;
  /** Set false to render plain cards. The shelf below decides whether its
   *  cards carry the library toggle; the catalog keeps it. */
  showLibraryControls?: boolean;
}) {
  return (
    <section className="section">
      <div className="section-heading">
        <div className={styles.shelfHeading}>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <Link href={href}>{linkLabel}</Link>
      </div>
      {items.length ? (
        <RailScroller railClassName={styles.posterRail}>{items.map((item) => <CatalogCard item={item} key={item.slug} variant="media" libraryControls={showLibraryControls} />)}</RailScroller>
      ) : (
        <div className="empty-state" role="status"><strong>{emptyLabel}</strong></div>
      )}
    </section>
  );
}

export default async function HomePage() {
  const todayKey = localDayKey(new Date());
  // Every block degrades to an empty shelf instead of a 500 when the API is
  // briefly unreachable, which also keeps the container healthcheck independent
  // from the Caddy -> API chain during cold starts.
  const [airing, popular, newest, schedule, recentEpisodes, { locale, t }] = await Promise.all([
    getAiringTitles().catch((): CatalogItem[] => []),
    getCatalog({ ordering: "popular", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getCatalog({ ordering: "recent", pageSize: SHELF_SIZE }).catch(() => emptyPage<CatalogItem>()),
    getSchedule(todayKey, addDays(todayKey, 2)).catch((): ScheduleResponse => emptyPage()),
    getRecentEpisodes(RECENT_EPISODE_DAYS).catch((): ScheduleItem[] => []),
    getI18n(),
  ]);
  // Release shelves come first: a returning viewer's daily question is "what
  // just came out", not "which universes exist".
  const hasDenseAiringShelf = airing.length >= MIN_VISIBLE_SHELF;
  // The shelves are filled from independent queries, so the same title can be
  // airing and popular at once. A repeated card on one screen reads as a data
  // bug, so each follower shelf drops what an earlier shelf already took.
  const popularShelfItems = dedupeShelf(hasDenseAiringShelf ? airing : [], popular.results);
  // The newest shelf prefers zero repeats, but deleting it whole left the
  // home page with nothing that pushes toward new titles. When a full dedup
  // leaves too few cards, it keeps only the lead shelf's exclusions and
  // tolerates overlap with the popular shelf — a repeated card is the lesser
  // evil next to an empty page.
  const newestFullyDeduped = dedupeShelf([...(hasDenseAiringShelf ? airing : []), ...popularShelfItems], newest.results);
  const newestShelfItems = newestFullyDeduped.length >= MIN_FULL_SHELF
    ? newestFullyDeduped
    : dedupeShelf(popularShelfItems, newest.results);

  return <PageShell active="home">
    <script nonce={(await headers()).get("x-nonce") ?? undefined} type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdScript(websiteJsonLd(locale)) }} />
      <div>
        <ContinueWatchingBlock catalogCount={popular.count} featured={popular.results[0] ?? airing[0]} />

        {/* Next franchise part sits right under the resume block: it is the
            same personal context, one step ahead. Silent for guests and when
            no started title has a franchise successor. */}
        <NextPartShelf />

        {/* The strip owns its section: it disappears whole when nothing upcoming
            is left for the window, so the page never shows an empty heading. */}
        <ScheduleStrip items={schedule.results} serverTodayKey={todayKey} />

      <RecentEpisodesRail items={recentEpisodes} serverTodayKey={todayKey} />

      {hasDenseAiringShelf && <AiringRail items={airing} />}

      <CatalogShelf
        title={t("home.popular")}
        subtitle={t("home.popularText")}
        items={popularShelfItems}
        href="/catalog"
        linkLabel={t("home.showAll")}
        emptyLabel={t("home.sectionEmpty")}
      />

      {/* Personal picks silently collapse for guests and cold accounts, so
          the shelf never adds a titled empty block. */}
      <RecommendationShelf />

      {/* The franchise rail used to sit here. Franchises are still part of the
          product — they are reachable from the catalog and from title pages —
          but as a home shelf they pushed the next real shelf below the fold. */}

      {newestShelfItems.length >= MIN_VISIBLE_SHELF && <CatalogShelf
        title={t("home.newest")}
        subtitle={t("home.newestText")}
        items={newestShelfItems}
        href="/catalog"
        linkLabel={t("home.showAll")}
        emptyLabel={t("home.sectionEmpty")}
        showLibraryControls={false}
      />}
    </div>
  </PageShell>;
}
